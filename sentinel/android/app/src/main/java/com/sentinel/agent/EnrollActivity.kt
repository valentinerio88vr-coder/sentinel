package com.sentinel.agent

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.ViewGroup
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

/**
 * Enrollment screen. This is the consent gate: no collection code runs until the person
 * holding the device reads the notice and ticks the box.
 */
class EnrollActivity : AppCompatActivity() {

    private val needed = buildList {
        add(Manifest.permission.READ_SMS)
        add(Manifest.permission.READ_CALL_LOG)
        add(Manifest.permission.ACCESS_FINE_LOCATION)
        add(Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
    }.toTypedArray()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Prefs.enabled(this) && Prefs.token(this) != null) {
            startActivity(Intent(this, StatusActivity::class.java)); finish(); return
        }

        val pad = (16 * resources.displayMetrics.density).toInt()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad * 2, pad, pad)
        }

        root.addView(TextView(this).apply {
            text = "Sentinel Agent"
            textSize = 24f
        })
        root.addView(TextView(this).apply {
            text = "Consent-based device monitoring"
            textSize = 13f
            setPadding(0, pad / 4, 0, pad)
        })

        val urlInput = EditText(this).apply {
            hint = "Server URL (https://sentinel.example.com)"
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            setText(Prefs.baseUrl(this@EnrollActivity))
        }
        val codeInput = EditText(this).apply {
            hint = "8-character enrollment code"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS
        }
        root.addView(urlInput)
        root.addView(codeInput)

        val scroll = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
            setPadding(0, pad, 0, pad)
        }
        val noticeText = TextView(this).apply {
            text = Collectors.CONSENT_NOTICE
            textSize = 13f
        }
        scroll.addView(noticeText)
        root.addView(scroll)

        val agree = CheckBox(this).apply {
            text = "I have read the notice above and I agree to this monitoring"
            textSize = 13f
        }
        root.addView(agree)

        val status = TextView(this).apply { textSize = 12f }
        root.addView(status)

        val btn = Button(this).apply { text = "Grant permissions" }
        root.addView(btn)

        setContentView(root)

        btn.setOnClickListener {
            if (!agree.isChecked) {
                status.text = "You must accept the notice before monitoring can start."
                return@setOnClickListener
            }
            val base = urlInput.text.toString().trim().trimEnd('/')
            val code = codeInput.text.toString().trim()
            if (!base.startsWith("http")) { status.text = "Enter a valid server URL."; return@setOnClickListener }
            if (code.length < 6) { status.text = "Enter the enrollment code from your administrator."; return@setOnClickListener }

            val missing = needed.filter {
                ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
            }
            if (missing.isNotEmpty()) {
                ActivityCompat.requestPermissions(this, missing.toTypedArray(), REQ_PERMS)
                pendingBase = base; pendingCode = code
                status.text = "Grant the permissions, then tap the button again."
                return@setOnClickListener
            }
            enroll(base, code, status, btn)
        }
    }

    private var pendingBase = ""
    private var pendingCode = ""

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_PERMS && pendingBase.isNotEmpty()) {
            val status = findViewById<TextView>(android.R.id.content).let { TextView(this) }
            if (grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
                enroll(pendingBase, pendingCode, null, null)
            } else {
                toast("Permissions denied — monitoring cannot start without them.")
            }
        }
    }

    private fun enroll(base: String, code: String, status: TextView?, btn: Button?) {
        btn?.isEnabled = false
        status?.text = "Enrolling…"
        Thread {
            try {
                val res = ApiClient.claim(base, code, Collectors.noticeHash(Collectors.CONSENT_NOTICE))
                Prefs.saveEnrollment(this, res.token, res.deviceId, res.label, base)
                if (Build.VERSION.SDK_INT >= 33 &&
                    ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                    != PackageManager.PERMISSION_GRANTED) {
                    // Ask for background location as a separate, explained step (Android 11+ requirement).
                    runOnUiThread { askBackgroundLocation(base, code, status, btn) }
                    return@Thread
                }
                goToStatus()
            } catch (e: Exception) {
                runOnUiThread {
                    btn?.isEnabled = true
                    status?.text = "Enrollment failed: ${e.message}"
                }
            }
        }.start()
    }

    private fun askBackgroundLocation(base: String, code: String, status: TextView?, btn: Button?) {
        AlertDialog.Builder(this)
            .setTitle("Allow location in the background?")
            .setMessage("To report last-known location between app launches, Android needs \"Allow all the time\". " +
                "You can skip this and monitoring will still work while the app is open.")
            .setPositiveButton("Continue") { _, _ ->
                if (Build.VERSION.SDK_INT >= 29) {
                    ActivityCompat.requestPermissions(
                        this, arrayOf(Manifest.permission.ACCESS_BACKGROUND_LOCATION), REQ_BG
                    )
                }
                goToStatus()
            }
            .setNegativeButton("Skip") { _, _ -> goToStatus() }
            .show()
    }

    private fun goToStatus() {
        startActivity(Intent(this, StatusActivity::class.java))
        finish()
    }

    private fun toast(m: String) = Toast.makeText(this, m, Toast.LENGTH_LONG).show()

    companion object {
        private const val REQ_PERMS = 1001
        private const val REQ_BG = 1002
    }
}
