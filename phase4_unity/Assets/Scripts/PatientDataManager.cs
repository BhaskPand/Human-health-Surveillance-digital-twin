// Assets/Scripts/PatientDataManager.cs
// Connects Unity to the FastAPI WebSocket server.
// Attach to an empty GameObject called "DigitalTwinManager".

using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using NativeWebSocket;  // Install: https://github.com/endel/NativeWebSocket

[Serializable]
public class InferenceResult
{
    public string label;
    public float  probability;
    public string risk;
    public float  confidence;
}

[Serializable]
public class PatientVitals
{
    public string          patient_id;
    public string          timestamp;
    public float           HR;
    public float           SpO2;
    public float           temperature;
    public float           movement;
    public int             fall;
    public InferenceResult inference;
}

public class PatientDataManager : MonoBehaviour
{
    [Header("Server Config")]
    public string serverIP    = "localhost";
    public int    serverPort  = 8000;
    public string patientID   = "patient_001";

    [Header("Status")]
    [SerializeField] private string connectionStatus = "Disconnected";
    [SerializeField] private string currentRisk      = "UNKNOWN";
    [SerializeField] private float  latestHR;
    [SerializeField] private float  latestSpO2;

    // ── Events (subscribe from VitalsUIController) ────────────────────────────
    public static event Action<PatientVitals> OnVitalsReceived;
    public static event Action<string>        OnConnectionStatusChanged;
    public static event Action                OnFallDetected;
    public static event Action<string>        OnAlertTriggered;   // "CRITICAL" | "WARNING"

    // ── Private ───────────────────────────────────────────────────────────────
    private WebSocket  _ws;
    private bool       _isReconnecting = false;
    private int        _reconnectDelay = 3;
    private const int  MAX_RECONNECT_DELAY = 30;

    private void Start()
    {
        Application.runInBackground = true;
        StartCoroutine(ConnectWebSocket());
    }

    private IEnumerator ConnectWebSocket()
    {
        string url = $"ws://{serverIP}:{serverPort}/ws/{patientID}";
        Debug.Log($"[DigitalTwin] Connecting to {url}");

        _ws = new WebSocket(url);

        _ws.OnOpen += () =>
        {
            connectionStatus = "Connected";
            _reconnectDelay  = 3;
            _isReconnecting  = false;
            Debug.Log("[DigitalTwin] WebSocket connected.");
            OnConnectionStatusChanged?.Invoke("Connected");
        };

        _ws.OnMessage += (bytes) =>
        {
            string json = System.Text.Encoding.UTF8.GetString(bytes);
            ParseVitals(json);
        };

        _ws.OnError += (err) =>
        {
            Debug.LogWarning($"[DigitalTwin] WS error: {err}");
        };

        _ws.OnClose += (code) =>
        {
            connectionStatus = "Disconnected";
            Debug.Log($"[DigitalTwin] WebSocket closed: {code}");
            OnConnectionStatusChanged?.Invoke("Disconnected");
            if (!_isReconnecting)
                StartCoroutine(Reconnect());
        };

        yield return _ws.Connect();
    }

    private void ParseVitals(string json)
    {
        try
        {
            PatientVitals vitals = JsonUtility.FromJson<PatientVitals>(json);
            if (vitals == null) return;

            // Update inspector fields
            latestHR    = vitals.HR;
            latestSpO2  = vitals.SpO2;
            currentRisk = vitals.inference?.risk ?? "UNKNOWN";

            // Dispatch events (always on main thread via Update queue)
            _pendingVitals.Enqueue(vitals);
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[DigitalTwin] JSON parse error: {ex.Message}");
        }
    }

    // Thread-safe event queue
    private readonly Queue<PatientVitals> _pendingVitals = new Queue<PatientVitals>();

    private void Update()
    {
        // Dispatch all pending vitals on the main thread
        while (_pendingVitals.Count > 0)
        {
            PatientVitals v = _pendingVitals.Dequeue();
            OnVitalsReceived?.Invoke(v);

            if (v.fall == 1)
                OnFallDetected?.Invoke();

            string risk = v.inference?.risk;
            if (risk == "CRITICAL" || risk == "WARNING")
                OnAlertTriggered?.Invoke(risk);
        }

#if !UNITY_WEBGL || UNITY_EDITOR
        _ws?.DispatchMessageQueue();
#endif
    }

    private IEnumerator Reconnect()
    {
        _isReconnecting = true;
        connectionStatus = $"Reconnecting in {_reconnectDelay}s…";
        Debug.Log($"[DigitalTwin] Reconnecting in {_reconnectDelay}s…");
        OnConnectionStatusChanged?.Invoke(connectionStatus);

        yield return new WaitForSeconds(_reconnectDelay);

        // Exponential backoff (cap at 30s)
        _reconnectDelay = Mathf.Min(_reconnectDelay * 2, MAX_RECONNECT_DELAY);

        StartCoroutine(ConnectWebSocket());
    }

    private void OnApplicationQuit()
    {
        _ws?.Close();
    }

    // ── Public API (called from other scripts or buttons) ─────────────────────
    public string GetCurrentRisk()      => currentRisk;
    public float  GetLatestHR()         => latestHR;
    public float  GetLatestSpO2()       => latestSpO2;
    public bool   IsConnected()         => _ws?.State == WebSocketState.Open;
}
