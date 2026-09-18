using System;

class BimanualFeedbackGateTest
{
    static int checks;
    static void Check(bool value, string message)
    {
        ++checks;
        if (!value) throw new Exception(message);
    }
    static void Main()
    {
        string a = new string('a', 32), b = new string('b', 32), c = new string('c', 32);
        var gate = new G1BimanualFeedbackGate();
        bool restarted;
        Check(gate.Accept(a, 100, 0, 8, 10, out restarted) && !restarted, "first backend");
        Check(!gate.Accept(a, 100, 0, 8, 10, out restarted), "duplicate state");
        Check(gate.Accept(a, 100, 1, 8, 10, out restarted), "new state same input ack");
        Check(!gate.Accept(a, 100, 2, 7, 10, out restarted), "reordered input ack");
        Check(!gate.Accept(a, 101, 2, 8, 10, out restarted), "same id changed start");
        Check(gate.Accept(b, 200, 0, 2, 10, out restarted) && restarted, "fast restart lower sequence");
        Check(!gate.Accept(a, 100, 999, 9, 10, out restarted), "old backend arrives late");
        Check(!gate.Accept(c, 150, 999, 9, 10, out restarted), "unseen old instance arrives late");
        Check(!gate.Accept(c, 200, 999, 9, 10, out restarted), "same timestamp different instance");
        Check(!gate.Accept(c, 300, 0, 10, 10, out restarted), "future input ack");
        Check(gate.BackendId == b && gate.StateSequence == 0, "rejections are atomic");
        Check(!gate.Accept(null, 300, 0, 1, 10, out restarted), "legacy missing generation");
        Check(!gate.Accept("bad", 300, 0, 1, 10, out restarted), "malformed generation");
        Check(!gate.Accept(c, 300, -1, 1, 10, out restarted), "negative state sequence");
        Check(!gate.Accept(c, 0, 0, 1, 10, out restarted), "invalid clock stamp");
        Check(gate.Accept(c, 300, 0, 3, 10, out restarted) && restarted, "next restart");
        Check(gate.Accept(c, 300, 1, 4, 10, out restarted) && !restarted, "normal after rearm");
        Console.WriteLine("PASS: " + checks + " backend generation/order checks");
    }
}
