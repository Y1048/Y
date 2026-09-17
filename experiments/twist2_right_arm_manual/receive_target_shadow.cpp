#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include "queued_input_offline.hpp"
#pragma comment(lib, "Ws2_32.lib")

// Windows loopback receiver only. Candidates go exclusively to a new local log.
// The same thread owns recv, the bounded queue, tick, stop state and log writes.
// No send/sendto, Unitree SDK, DDS, policy or physical controller dependencies.
class LocalReceiver
{
    bool initialized = false;

public:
    SOCKET socket_handle = INVALID_SOCKET;
    WSAEVENT ready_event = WSA_INVALID_EVENT;
    LocalReceiver() = default;
    LocalReceiver(const LocalReceiver&) = delete;
    LocalReceiver& operator=(const LocalReceiver&) = delete;
    void Open(int port)
    {
        WSADATA data{};
        if (WSAStartup(MAKEWORD(2, 2), &data) != 0) throw std::runtime_error("winsock_start_failed");
        initialized = true;
        socket_handle = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
        if (socket_handle == INVALID_SOCKET) throw std::runtime_error("socket_failed");
        BOOL exclusive = TRUE;
        u_long nonblocking = 1;
        sockaddr_in address{};
        address.sin_family = AF_INET;
        address.sin_port = htons(static_cast<unsigned short>(port));
        address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        if (setsockopt(socket_handle, SOL_SOCKET, SO_EXCLUSIVEADDRUSE,
                reinterpret_cast<char*>(&exclusive), sizeof(exclusive)) != 0
            || ioctlsocket(socket_handle, FIONBIO, &nonblocking) != 0
            || bind(socket_handle, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0)
            throw std::runtime_error("bind_or_socket_configuration_failed");
        ready_event = WSACreateEvent();
        if (ready_event == WSA_INVALID_EVENT
            || WSAEventSelect(socket_handle, ready_event, FD_READ) != 0)
            throw std::runtime_error("socket_event_failed");
    }
    ~LocalReceiver()
    {
        if (socket_handle != INVALID_SOCKET) closesocket(socket_handle);
        if (ready_event != WSA_INVALID_EVENT) WSACloseEvent(ready_event);
        if (initialized) WSACleanup();
    }
};

class TickTimer
{
public:
    HANDLE handle = CreateWaitableTimerExW(nullptr, nullptr,
        CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_MODIFY_STATE | SYNCHRONIZE);
    TickTimer()
    {
        if (!handle) throw std::runtime_error("high_resolution_timer_unavailable");
    }
    TickTimer(const TickTimer&) = delete;
    TickTimer& operator=(const TickTimer&) = delete;
    ~TickTimer() { CloseHandle(handle); }
    void Arm(double seconds)
    {
        LARGE_INTEGER due{};
        due.QuadPart = -std::max(1LL, static_cast<long long>(std::ceil(seconds * 10000000)));
        if (!SetWaitableTimer(handle, &due, 0, nullptr, nullptr, FALSE))
            throw std::runtime_error("tick_timer_failed");
    }
};

class NewLog
{
    HANDLE handle;

public:
    explicit NewLog(const std::filesystem::path& path)
        : handle(CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                             CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr))
    {
        if (handle == INVALID_HANDLE_VALUE) throw std::runtime_error("new_log_required");
    }
    NewLog(const NewLog&) = delete;
    NewLog& operator=(const NewLog&) = delete;
    ~NewLog() { CloseHandle(handle); }
    void Write(const nlohmann::json& row)
    {
        const std::string text = row.dump() + "\n";
        DWORD written = 0;
        if (!WriteFile(handle, text.data(), static_cast<DWORD>(text.size()), &written, nullptr)
            || written != text.size() || !FlushFileBuffers(handle))
            throw std::runtime_error("output_write_error");
    }
};

std::string Hex(const char* data, int size)
{
    constexpr char digits[] = "0123456789abcdef";
    std::string result;
    result.reserve(static_cast<std::size_t>(size) * 2);
    for (int i = 0; i < size; ++i)
    {
        const auto byte = static_cast<unsigned char>(data[i]);
        result.push_back(digits[byte >> 4]);
        result.push_back(digits[byte & 15]);
    }
    return result;
}

int Integer(const wchar_t* value)
{
    std::size_t count = 0;
    const int result = std::stoi(value, &count);
    if (count != std::wstring(value).size()) throw std::invalid_argument("invalid_integer");
    return result;
}

int wmain(int argc, wchar_t** argv)
{
    try
    {
        if (argc != 5)
            throw std::invalid_argument("Usage: receive_target_shadow PORT SECONDS CONFIG_JSON NEW_LOG_JSONL");
        const int port = Integer(argv[1]);
        const int duration = Integer(argv[2]);
        if (port < 1024 || port > 65535 || duration < 1 || duration > 180)
            throw std::invalid_argument("port_or_duration_range");
        std::ifstream config_file{std::filesystem::path(argv[3])};
        const auto config = nlohmann::json::parse(config_file);
        if (config.at("schema") != "g1.twist2.cpp_receive_shadow.v1")
            throw std::invalid_argument("simulation_config_required");
        std::optional<std::array<double, 29>> q;
        if (config.at("baseline_source") == "explicit_simulation_baseline")
        {
            const auto baseline = config.at("baseline").get<std::vector<double>>();
            if (baseline.size() != 29) throw std::invalid_argument("baseline_count");
            q.emplace();
            std::copy(baseline.begin(), baseline.end(), q->begin());
        }
        else if (config.at("baseline_source") != "first_active_mink_simulation_not_g1"
                 || config.contains("baseline"))
            throw std::invalid_argument("simulation_baseline_source_required");
        if (!config.at("queue_capacity").is_number_unsigned())
            throw std::invalid_argument("invalid_queue_capacity");
        QueuedInputOffline queue(q, 0, config.at("maximum_delta_rad"), config.at("queue_capacity"));
        LocalReceiver receiver;
        receiver.Open(port);
        TickTimer timer;
        NewLog log{std::filesystem::path(argv[4])};
        log.Write({{"event", "config"}, {"log_schema", "g1.twist2.receive_replay.v1"}, {"config", config}, {"port", port},
            {"duration_s", duration}, {"hardware_output_authorized", false},
            {"publisher_created", false}, {"robot_command_sent", false},
            {"timer", "process_high_resolution_waitable_timer"},
            {"tick_period_s", .02}, {"max_payload_bytes", QueuedInputOffline::kMaximumPayloadBytes}});
        const auto start = std::chrono::steady_clock::now();
        const auto Now = [&start]()
        {
            return std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        };
        std::cout << "READY 127.0.0.1:" << port << " SHADOW ONLY; NO ROBOT OUTPUT" << std::endl;
        double next_tick = .02;
        std::size_t packet_count = 0;
        std::size_t active_ticks = 0;
        // Capture complete IPv4 UDP datagrams, including application-oversize input.
        std::vector<char> buffer(65536);
        const auto Record = [&](const char* event, double now, const std::string& mode,
                                std::size_t batch_size)
        {
            log.Write({{"event", event}, {"now_s", now}, {"mode", mode},
                {"reason", queue.Reason()},
                {"validated_goal", queue.Goal() ? nlohmann::json(*queue.Goal()) : nlohmann::json(nullptr)},
                {"q", queue.HasBaseline() ? nlohmann::json(queue.Target()) : nlohmann::json(nullptr)},
                {"baseline", queue.Baseline() ? nlohmann::json(*queue.Baseline()) : nlohmann::json(nullptr)},
                {"baseline_captured", queue.HasBaseline()}, {"batch_size", batch_size},
                {"packets", packet_count}, {"active_ticks", active_ticks}, {"queue_peak", queue.Peak()},
                {"hardware_output_authorized", false}, {"publisher_created", false}});
        };
        try
        {
            while (queue.Reason().empty())
            {
                const double now = Now();
                if (now >= duration) { queue.Stop("duration_limit"); break; }
                if (now >= next_tick)
                {
                    const bool had_baseline = queue.HasBaseline();
                    const auto batch_size = queue.Depth();
                    const auto mode = queue.Tick(now);
                    if (!had_baseline && queue.HasBaseline())
                        std::cout << "BASELINE first active Mink simulation; NOT G1 LowState" << std::endl;
                    if (mode == "active") ++active_ticks;
                    Record("tick", now, mode, batch_size);
                    // Never run catch-up ticks back-to-back after a delayed tick.
                    next_tick = now + .02;
                    continue;
                }
                timer.Arm(std::min(next_tick, static_cast<double>(duration)) - now);
                const HANDLE events[] = {timer.handle, receiver.ready_event};
                const DWORD selected = WaitForMultipleObjects(2, events, FALSE, INFINITE);
                if (selected == WAIT_OBJECT_0) continue;
                if (selected != WAIT_OBJECT_0 + 1) { queue.Stop("wait_error"); break; }
                WSANETWORKEVENTS network_events{};
                if (WSAEnumNetworkEvents(receiver.socket_handle, receiver.ready_event, &network_events) != 0
                    || network_events.iErrorCode[FD_READ_BIT] != 0)
                {
                    queue.Stop("receive_event_error");
                    break;
                }
                // Each drain is bounded by capacity + 1: sustained floods latch
                // overflow rather than starving the tick or hiding a release.
                while (queue.Reason().empty())
                {
                    const int size = recv(receiver.socket_handle, buffer.data(),
                                          static_cast<int>(buffer.size()), 0);
                    const int receive_error = size == SOCKET_ERROR ? WSAGetLastError() : 0;
                    const double received = Now();
                    if (size == SOCKET_ERROR)
                    {
                        if (receive_error != WSAEWOULDBLOCK)
                            queue.Stop(receive_error == WSAEMSGSIZE ? "datagram_too_large" : "receive_error");
                        break;
                    }
                    ++packet_count;
                    const bool expired = received >= duration;
                    if (expired) queue.Stop("duration_limit");
                    const bool accepted = !expired && queue.Enqueue(std::string(buffer.data(), size), received);
                    log.Write({{"event", "packet"}, {"packet", packet_count},
                        {"received_at_s", received}, {"payload_hex", Hex(buffer.data(), size)},
                        {"size_bytes", size}, {"enqueued", accepted}, {"expired", expired},
                        {"reason", queue.Reason()}});
                    if (!accepted) break;
                }
            }
        }
        catch (const std::exception& error)
        {
            queue.Stop(error.what());
            // On a log I/O failure, stderr is the remaining reporting channel.
            std::cerr << "STOP " << queue.Reason() << std::endl;
            return 2;
        }
        Record("final", Now(), "stopped", 0);
        std::cout << "STOP " << queue.Reason() << std::endl;
        return (queue.Reason() == "input_disengaged"
            || (queue.Reason() == "duration_limit" && packet_count > 0)) ? 0 : 2;
    }
    catch (const std::exception& error)
    {
        std::cerr << "STOP " << error.what() << std::endl;
        return 2;
    }
}
