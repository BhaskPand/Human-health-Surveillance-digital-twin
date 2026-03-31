// Assets/Scripts/HeartbeatAnimator.cs
// Pulses a 3D heart model or any object at the patient's actual heart rate.

using UnityEngine;

public class HeartbeatAnimator : MonoBehaviour
{
    [Header("Target")]
    [Tooltip("The heart model or UI element to animate. Defaults to this GameObject.")]
    public Transform target;

    [Header("Beat Settings")]
    [Range(0.05f, 0.5f)]
    public float beatScale   = 0.15f;    // scale factor added on beat
    public float attackTime  = 0.06f;    // seconds to expand
    public float releaseTime = 0.12f;    // seconds to contract

    [Header("Color Flash (optional)")]
    public Renderer heartRenderer;        // leave null to skip
    public Color    normalColor   = Color.red;
    public Color    flashColor    = new Color(1f, 0.3f, 0.3f);

    // ── Runtime ──────────────────────────────────────────────────────────────
    private float _bpm            = 72f;
    private float _beatInterval   => 60f / _bpm;
    private float _timer          = 0f;
    private bool  _expanding      = false;
    private float _phaseTimer     = 0f;
    private Vector3 _baseScale;

    private void Awake()
    {
        if (target == null) target = transform;
        _baseScale = target.localScale;

        PatientDataManager.OnVitalsReceived += v => _bpm = v.HR;
    }

    private void OnDestroy()
    {
        PatientDataManager.OnVitalsReceived -= v => _bpm = v.HR;
    }

    private void Update()
    {
        _timer += Time.deltaTime;

        // Trigger beat
        if (_timer >= _beatInterval)
        {
            _timer      = 0f;
            _expanding  = true;
            _phaseTimer = 0f;
        }

        // Animate
        if (_expanding)
        {
            _phaseTimer += Time.deltaTime;
            float t = _phaseTimer / attackTime;

            if (t < 1f)
            {
                // Expand
                float s = 1f + beatScale * Mathf.Sin(t * Mathf.PI * 0.5f);
                target.localScale = _baseScale * s;

                if (heartRenderer)
                    heartRenderer.material.color =
                        Color.Lerp(normalColor, flashColor, t);
            }
            else
            {
                // Contract
                float t2 = (_phaseTimer - attackTime) / releaseTime;
                float s  = 1f + beatScale * (1f - Mathf.Sin(t2 * Mathf.PI * 0.5f));
                target.localScale = _baseScale * Mathf.Max(1f, s);

                if (heartRenderer)
                    heartRenderer.material.color =
                        Color.Lerp(flashColor, normalColor, t2);

                if (t2 >= 1f)
                {
                    _expanding        = false;
                    target.localScale = _baseScale;
                    if (heartRenderer) heartRenderer.material.color = normalColor;
                }
            }
        }
    }

    // Call from inspector or another script to force a beat
    public void ForceBeat() { _timer = _beatInterval; }
}
