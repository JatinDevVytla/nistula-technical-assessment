# Part 3 — Thinking Question

**Scenario:** It is 3 AM. A guest at Villa B1 sends a WhatsApp message:
> "There is no hot water and we have guests arriving for breakfast in 4 hours. This is unacceptable. I want a refund for tonight."

---

## Question A — The Immediate Response

**The message the AI sends right now:**

> Hi! I'm so sorry — I completely understand how stressful this is, especially with guests arriving in just a few hours.
>
> I've flagged this as urgent right now and our caretaker will be contacted immediately. You should hear back within the next 15–20 minutes with a plan to get the hot water restored tonight.
>
> On the refund request — I've noted it and it will be reviewed by our team first thing. We'll make sure you're treated fairly.
>
> I'm sorry again. We'll get this sorted.

**Why this wording:**
The guest is stressed and time-pressured — the response leads with empathy, not policy. It gives a concrete next step (caretaker contacted, 15–20 min) so the guest feels heard and not abandoned at 3am. The refund is acknowledged without making a promise the AI has no authority to keep, which avoids a dispute later.

---

## Question B — The System Design

Beyond sending the message, the platform should trigger a full escalation chain:

1. **Classify and flag** — The message scores below 0.60 and is tagged `complaint`. Action is set to `escalate` automatically. No AI auto-send.

2. **Notify the caretaker** — An automated WhatsApp or SMS is sent to the caretaker with the guest's name, villa, issue, and a timestamp. If the caretaker does not acknowledge within 15 minutes, the notification escalates to the on-call property manager.

3. **Notify the Nistula ops team** — Slack or email alert fires to the duty team with the full conversation thread and the guest's booking details.

4. **Log everything** — The message, the AI draft, the escalation trigger, and every subsequent action are written to the database with timestamps. The `agent_actions` table records who took over and when.

5. **If no human responds within 30 minutes** — The system sends a follow-up message to the guest: *"Our team is actively working on this. You will receive an update within the next 10 minutes."* This keeps the guest informed and reduces the chance they escalate to a negative review. A second, higher-priority alert fires to the property manager's personal phone.

6. **Resolution tracking** — The conversation stays `is_resolved = false` until a team member manually marks it resolved. This prevents it from falling through the cracks.

---

## Question C — The Learning

This is the third hot water complaint at Villa B1 in two months. The system should:

**Detect the pattern automatically.** A recurring issue detector runs weekly across all resolved complaints. If the same property + same issue category appears three or more times in 60 days, it flags a pattern and creates a maintenance ticket in the property management system.

**What I would build to prevent a fourth complaint:**

- **Scheduled maintenance prompts** — After the second complaint, the system automatically schedules a boiler inspection for Villa B1 and sends a reminder to the caretaker one week before the next check-in.
- **Pre-arrival checklist** — Add a hot water check to the caretaker's pre-check-in checklist. The caretaker confirms it is working before each new guest arrives. This is a 30-second check that eliminates the risk entirely.
- **Property health dashboard** — A simple internal dashboard that shows recurring complaint patterns per property, so the operations team can spot and act on issues proactively rather than reactively.

The goal is to move from *respond and recover* to *predict and prevent*. A complaint at 3am is a system failure — it means something that could have been caught during daylight hours was not.
