#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include "validate_input.hpp"
#pragma comment(lib, "Ws2_32.lib")

// Receive-only probe: optional JSON validation, never applies targets.
int main(int argc, char** argv)
{
    if (argc != 4 && !(argc == 5 && std::string(argv[4]) == "--validate"))
    {
        std::cerr << "Usage: receive_only PORT DURATION_SECONDS NEW_OUTPUT_FILE [--validate]\n";
        return 2;
    }
    int port = 0;
    int duration = 0;
    try
    {
        std::size_t count = 0;
        port = std::stoi(argv[1], &count);
        if (count != std::string(argv[1]).size()) return 2;
        duration = std::stoi(argv[2], &count);
        if (count != std::string(argv[2]).size()) return 2;
    }
    catch (...) { return 2; }
    if (port < 1024 || port > 65535 || duration < 1 || duration > 180) return 2;
    if (std::ifstream(argv[3]).good()) return 2;
    WSADATA data{};
    if (WSAStartup(MAKEWORD(2, 2), &data) != 0) return 2;
    SOCKET receiver = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    BOOL exclusive = TRUE;
    DWORD timeout = 100;
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(static_cast<unsigned short>(port));
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (receiver == INVALID_SOCKET
        || setsockopt(receiver, SOL_SOCKET, SO_EXCLUSIVEADDRUSE,
            reinterpret_cast<char*>(&exclusive), sizeof(exclusive)) != 0
        || setsockopt(receiver, SOL_SOCKET, SO_RCVTIMEO,
            reinterpret_cast<char*>(&timeout), sizeof(timeout)) != 0
        || bind(receiver, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0)
    {
        std::cerr << "BIND FAILED: " << WSAGetLastError() << "\n";
        closesocket(receiver);
        WSACleanup();
        return 2;
    }
    std::ofstream output(argv[3], std::ios::binary);
    if (!output)
    {
        closesocket(receiver);
        WSACleanup();
        return 2;
    }
    std::cout << "READY 127.0.0.1:" << port
        << " RECEIVE ONLY; NO SDK / POLICY / ROBOT OUTPUT" << std::endl;
    auto start = std::chrono::steady_clock::now();
    std::vector<char> buffer(65536);
    int packets = 0;
    int result = 0;
    InputValidator validator;
    bool validation = argc == 5;
    while (std::chrono::steady_clock::now() - start < std::chrono::seconds(duration))
    {
        int size = recv(receiver, buffer.data(), static_cast<int>(buffer.size()), 0);
        double now = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        if (validation && !validator.CheckTimeout(now).empty())
        {
            std::cerr << "STOP receiver_timeout\n";
            result = 2;
            break;
        }
        if (size == SOCKET_ERROR)
        {
            if (WSAGetLastError() == WSAETIMEDOUT) continue;
            result = 2;
            break;
        }
        // Network-order length prefix preserves datagram boundaries and raw bytes.
        unsigned long length = htonl(static_cast<unsigned long>(size));
        output.write(reinterpret_cast<char*>(&length), 4);
        output.write(buffer.data(), size);
        output.flush();
        if (!output) { result = 2; break; }
        ++packets;
        if (validation)
        {
            auto reason = validator.Validate(std::string(buffer.data(), size), now);
            if (reason == "waiting") continue;
            if (!reason.empty())
            {
                std::cerr << "STOP " << reason << std::endl;
                result = 2;
                break;
            }
            std::cout << "VALIDATED " << packets << std::endl;
        }
    }
    closesocket(receiver);
    WSACleanup();
    std::cout << "packets=" << packets << " output=" << argv[3] << std::endl;
    return result != 0 || packets == 0 ? 2 : 0;
}
