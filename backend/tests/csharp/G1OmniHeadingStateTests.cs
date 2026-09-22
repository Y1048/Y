using System;

public static class G1OmniHeadingStateTests
{
    private static int count;
    private static void Check(bool value) { ++count; if (!value) throw new Exception("Check " + count); }
    public static void Main()
    {
        var state = new G1OmniHeadingState();
        Check(state.Accept("a", new double[] { 0, 10, 112 }, 20));
        Check(state.Degrees == 0); // absolute starting heading is not a jump
        Check(state.Accept("a", new double[] { 1, 10.1, 142 }, 20.1));
        Check(Math.Abs(state.Degrees - 30) < 1e-8);
        Check(!state.Accept("a", new double[] { 1, 10.1, 142 }, 20.1));
        Check(!state.Accept("a", new double[] { 2, 10.2, double.NaN }, 20.2));
        Check(!state.Accept("a", new double[] { 2, 10.2, 300 }, 20.2));
        Check(state.Degrees == 30);
        Check(state.Accept("a", new double[] { 2, 11, 300 }, 21)); // stale gap rebase
        Check(state.Degrees == 30);
        Check(state.Accept("b", new double[] { 0, 1, 0 }, 21.1)); // new clock/session
        Check(!state.Accept("a", new double[] { 3, 11.2, 301 }, 21.2));
        Check(state.Accept("b", new double[] { 1, 1.1, 330 }, 21.2));
        Check(Math.Abs(state.Degrees) < 1e-8); // wrap 0 -> 330 is -30
        Check(!state.Accept("b", new double[] { 2, 1, 335 }, 21.3));
        Check(!state.Accept("b", new double[] { 2, 1.2, 335 }, 20));
        Check(!state.Accept("b", null, 22));
        Check(!state.Accept("b", new double[] { 3, 4 }, 22));
        Check(G1OmniHeadingState.Delta(1, 359) == 2);
        Check(G1OmniHeadingState.Delta(359, 1) == -2);
        Check(G1OmniHeadingState.ToUnityYawDelta(30) == -30); // G1 left -> Unity left
        Check(G1OmniHeadingState.ToUnityYawDelta(-30) == 30); // G1 right -> Unity right
        Console.WriteLine("PASS: " + count + " production heading-gate assertions");
    }
}
