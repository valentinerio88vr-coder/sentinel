# Deploying Sentinel lawfully

Sentinel is a monitoring platform. Monitoring is legal in many contexts and criminal in others, and
the line is almost always drawn at **consent and notice**, not at the technology. This document is
engineering guidance, not legal advice — get a lawyer's sign-off for your jurisdiction before you
point this at a real device.

---

## The three lawful bases, and what each requires

### 1. Informed consent of the person carrying the device (adults)

Valid when the person is a competent adult who understands what is collected and can refuse.
Sentinel enforces the mechanics: on-device notice, explicit checkbox, `consent_at`/`consent_ip`
record, permanent notification, one-tap stop.

What it does not prove: that consent was voluntary. If someone consents because they fear losing
their job, that consent may be void. Keep the notice plain-language and the alternative real.

**Never** enroll a partner's, spouse's, employee's or family member's phone by entering the code
yourself. That is the exact fact pattern in most stalkerware prosecutions.

### 2. Parental authority over your own minor child  ← this build targets this case

Defensible in most jurisdictions for a child in your care, up to roughly 16–18 depending on where
you live. Requirements:
- The child is a minor and in your custody, and the phone is one you own and pay for.
- Be transparent — tell them it's installed. Covert tracking of a teenager damages the relationship
  and, in several jurisdictions (e.g. some EU member states), is unlawful regardless of custody.
- Age-appropriate notice, written for the child, not for a lawyer. The Android agent's consent screen
  is written at roughly a 12-year-old reading level on purpose.
- Stop when they turn 18 — at that point consent, not parental authority, is the only lawful basis,
  and they are entitled to have the app removed.

Practical guidance that matters more than the legal theory:
- Install it **together**, sitting next to them. The seed script's onboarding copy says this too.
- Tell them what triggers an alert before it happens (school arrival, SOS), so an alert is never a
  surprise interrogation.
- Do not use message content as the first move in a conflict. Location and SOS are the safety
  features; reading a 15-year-old's messages is a different act with a different cost.
- Remember the child can stop sharing, by design. If they do, that is information — treat it as a
  conversation, not a technical failure to route around.

### 3. Company-owned devices, with notice to employees

Defensible if:
- The device is owned and issued by the employer.
- Employees are told in writing, before use, what is monitored and why (handbook + a signed
  acknowledgment referencing this app by name).
- Monitoring is **proportionate** — call logs and location for a field fleet is defensible;
  reading personal SMS on a device employees also use personally often is not.
- Works councils / employee representatives are consulted where required (much of the EU).

If employees use their own phones (BYOD), you are in consent territory, and consent in an employment
relationship is unreliable in the EU and UK. Prefer a dedicated company device.

---

## Jurisdiction notes

### India
- **IT Act 2000, §66** — unauthorised access / data theft. Installing this on someone's phone without
  permission is squarely in scope.
- **DPDP Act 2023** — requires a lawful basis, purpose limitation, data minimisation, breach
  notification, and erasure on withdrawal. Sentinel's audit log, export endpoint and hard-delete
  support these duties; the retention policy is yours to set.
- **Puttaswamy (2017)** — informational privacy is a fundamental right; courts expect necessity and
  proportionality.
- Home/employer monitoring has some latitude, but SMS content on a personal phone generally does not.
- Employees must be notified; covert workplace monitoring has attracted penalties.

### European Union / UK
- **GDPR Art. 6** lawful basis (usually legitimate interests, with a documented balancing test),
  **Art. 13/14** transparency, **Art. 15** access, **Art. 17** erasure, **Art. 20** portability.
- A **DPIA is effectively mandatory** — systematic monitoring is explicitly a high-risk trigger
  (Art. 35(3)(a)). Do it before deployment, not after.
- Employee consent is rarely valid due to power imbalance — use legitimate interests + consultation.
- Some states criminalise covert tracking outright even within families.

### United States
- Federal: **ECPA / Wiretap Act** and **Stored Communications Act** — intercepting electronic
  communications without consent is a federal crime; penalties include imprisonment.
- **CFAA** — unauthorised access to a computer (a phone counts).
- State law varies sharply; California, New York and Washington are stricter. Several states
  criminalise installing tracking software on another adult's phone, full stop.
- **FTC Act §5** applies if you sell monitoring as a product — deceptive claims about stealth or
  consent draw enforcement.

---

## Features that were deliberately left out

Requests to add these will be declined, because each converts a monitoring tool into spyware:

| Not included | Why |
|---|---|
| Hiding the app icon / fake launcher | Removes the person's ability to know and to stop. Core stalkerware behaviour. |
| Killing the ongoing notification | Android requires it for foreground services; suppressing it is deception. |
| Remote microphone / camera / screen recording | Intercepts private space and third parties who never consented. Criminal wiretap exposure. |
| Reading WhatsApp / Signal / Telegram messages | Breaks end-to-end encryption via root or accessibility abuse; violates the SCA. |
| Keylogging / screenshots | Captures passwords and banking credentials — the highest-harm capability. |
| Collecting OTPs / SMS with passcodes | This is credentials theft. The Android collector **filters these out on-device**. |
| Surviving uninstall / device-admin lock | Turns the device into something the owner can't control. |
| Covert GPS "find my partner" mode | The single most common stalkerware use case. |
| Hiding the app from the child who carries the phone | Turns a parental tool into surveillance the child cannot see or stop. |
| Reading the child's messages without telling them | The notice covers it; hiding *that it is happening* is the line. |

If your requirement genuinely needs one of these, the honest answer is that you need a
different legal framework — a court order, a forensic warrant, or an MDM enrolled on company
hardware with full disclosure — not a different app.

---

## Pre-deployment checklist

- [ ] Written lawful basis documented and approved, per device or device class
- [ ] Notice text reviewed by counsel and shown on-device before any collection
- [ ] DPIA completed (EU) / privacy notice published
- [ ] Retention period defined, with an automated purge
- [ ] Consent withdrawal path tested end-to-end (it's the **Stop monitoring** button)
- [ ] Access-controlled operator accounts; 2FA enabled; leavers deprovisioned
- [ ] Export-on-request process ready (the `Export data` button is the answer)
- [ ] Breach notification runbook written
- [ ] Only devices you own or have documented consent for are enrolled

The last item is the one that matters most. Everything else is recoverable; that one is not.
