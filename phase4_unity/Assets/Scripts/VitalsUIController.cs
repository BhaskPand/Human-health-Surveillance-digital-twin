// Assets/Scripts/VitalsUIController.cs
// Updates all Unity UI elements with live patient vitals.
// Assign all Text/Slider references in Inspector.

using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using TMPro;            // TextMeshPro (preferred for hospital UI)

public class VitalsUIController : MonoBehaviour
{
    [Header("Vital Text Fields")]
    public TMP_Text hrText;
    public TMP_Text spo2Text;
    public TMP_Text tempText;
    public TMP_Text movementText;
    public TMP_Text riskText;
    public TMP_Text timestampText;
    public TMP_Text connectionText;

    [Header("Risk Probability")]
    public Slider    riskSlider;          // 0–1 range
    public Image     riskSliderFill;
    public TMP_Text  riskPercentText;

    [Header("Alert Panel")]
    public GameObject alertBanner;        // Enable/disable
    public TMP_Text   alertBannerText;
    public Image      alertBannerBg;

    [Header("Patient Avatar")]
    public Renderer[] avatarRenderers;    // body mesh(es) — tint by risk

    [Header("Colors")]
    public Color normalColor   = new Color(0.0f, 0.83f, 0.67f); // teal
    public Color warningColor  = new Color(0.96f, 0.62f, 0.04f); // amber
    public Color criticalColor = new Color(0.93f, 0.27f, 0.27f); // red
    public Color fallColor     = new Color(0.23f, 0.51f, 0.96f); // blue

    // ── Internal ─────────────────────────────────────────────────────────────
    private static readonly int EmissionColor = Shader.PropertyToID("_EmissionColor");
    private Coroutine _alertHideCoroutine;

    private void OnEnable()
    {
        PatientDataManager.OnVitalsReceived       += HandleVitals;
        PatientDataManager.OnConnectionStatusChanged += HandleConnectionStatus;
        PatientDataManager.OnFallDetected          += HandleFall;
        PatientDataManager.OnAlertTriggered        += HandleAlert;
    }

    private void OnDisable()
    {
        PatientDataManager.OnVitalsReceived        -= HandleVitals;
        PatientDataManager.OnConnectionStatusChanged -= HandleConnectionStatus;
        PatientDataManager.OnFallDetected           -= HandleFall;
        PatientDataManager.OnAlertTriggered         -= HandleAlert;
    }

    // ── Handlers ─────────────────────────────────────────────────────────────

    private void HandleVitals(PatientVitals v)
    {
        // Text fields
        SetText(hrText,        $"{v.HR:F1} bpm");
        SetText(spo2Text,      $"{v.SpO2:F1} %");
        SetText(tempText,      $"{v.temperature:F1} °C");
        SetText(movementText,  $"{v.movement:F2} g");
        SetText(timestampText, $"Updated: {v.timestamp?[11..19]}");

        // Risk
        string risk  = v.inference?.risk ?? "UNKNOWN";
        float  prob  = v.inference?.probability ?? 0f;

        SetText(riskText, risk);
        Color riskCol = RiskColor(risk);
        if (riskText) riskText.color = riskCol;

        // Slider
        if (riskSlider)       riskSlider.value = prob;
        if (riskSliderFill)   riskSliderFill.color = riskCol;
        if (riskPercentText)  riskPercentText.text = $"{prob*100:F0}%";

        // Avatar tint
        TintAvatar(riskCol);
    }

    private void HandleConnectionStatus(string status)
    {
        SetText(connectionText, status);
        if (connectionText)
            connectionText.color = status == "Connected"
                ? normalColor : criticalColor;
    }

    private void HandleFall()
    {
        ShowAlert("🚨 FALL DETECTED", fallColor, 5f);
    }

    private void HandleAlert(string risk)
    {
        string msg = risk == "CRITICAL"
            ? "⚠️ CRITICAL — Immediate attention required"
            : "⚠️ WARNING — Monitor closely";
        ShowAlert(msg, RiskColor(risk), 3f);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private void ShowAlert(string message, Color color, float duration)
    {
        if (alertBanner == null) return;

        SetText(alertBannerText, message);
        if (alertBannerBg) alertBannerBg.color = new Color(color.r, color.g, color.b, 0.85f);

        alertBanner.SetActive(true);

        if (_alertHideCoroutine != null)
            StopCoroutine(_alertHideCoroutine);
        _alertHideCoroutine = StartCoroutine(HideAlertAfter(duration));
    }

    private IEnumerator HideAlertAfter(float seconds)
    {
        yield return new WaitForSeconds(seconds);
        if (alertBanner) alertBanner.SetActive(false);
    }

    private void TintAvatar(Color color)
    {
        if (avatarRenderers == null) return;
        foreach (var r in avatarRenderers)
        {
            if (r == null) continue;
            r.material.color          = Color.Lerp(r.material.color, color, Time.deltaTime * 3f);
            r.material.SetColor(EmissionColor, color * 0.25f);
        }
    }

    private Color RiskColor(string risk) => risk switch
    {
        "CRITICAL" => criticalColor,
        "WARNING"  => warningColor,
        "FALL"     => fallColor,
        _          => normalColor
    };

    private static void SetText(TMP_Text field, string value)
    {
        if (field) field.text = value;
    }
}
