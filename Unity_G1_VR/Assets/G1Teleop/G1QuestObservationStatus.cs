using UnityEngine;
using UnityEngine.UI;

public sealed class G1QuestObservationStatus : MonoBehaviour
{
    public G1QuestObservationSender sender;
    private Text text;
    private void Awake() { text = GetComponent<Text>(); }
    private void Update() { if (text != null && sender != null) text.text = sender.Status; }
}
