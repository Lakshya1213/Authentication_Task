import asyncio
import json
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import SessionLocal
from transcript_agent.service import TranscriptAgentService

transcript_text = """
Salesperson: Hi Rohan, thanks for joining. Before we begin, is this still a good time?

Customer: Yes, this works. I have around 35 minutes.

Salesperson: Great. Just to confirm, you’re Head of Sales Operations at Northstar Fintech, right?

Customer: Yes. I lead sales operations and CRM process improvement. Our VP Sales, Meera Rao, will be the final business approver, but I’m driving the evaluation.

Salesperson: Got it. Can you give me a little context on what triggered this evaluation?

Customer: We’re scaling our enterprise sales team from 45 reps to around 80 reps this year. Right now, CRM hygiene is becoming a serious problem. Reps are not updating HubSpot properly, managers do not trust the pipeline, and follow-ups are often missed.

Salesperson: Understood. What CRM are you using today?

Customer: We use HubSpot Sales Hub Enterprise. It is integrated with Gmail, Google Calendar, and Slack. We also use Aircall for calling.

Salesperson: What is the biggest pain today?

Customer: The biggest issue is that sales conversations contain very useful information, but it never reaches CRM. Reps write very generic notes like “good call” or “follow-up needed.” We want call intelligence to automatically update deal context, next steps, and tasks.

Salesperson: That makes sense. Are you looking more for call recording analytics or CRM automation?

Customer: CRM automation is the bigger priority. Analytics is useful, but if it does not improve execution, managers won’t use it.

Salesperson: What kind of deal information do you want updated automatically?

Customer: Deal amount, expected close date, next step, decision process, competitor mentioned, and risk notes. If the customer asks for a proposal or demo, we want tasks created automatically.

Salesperson: Do you currently have custom fields in HubSpot for competitor and risk?

Customer: Yes, we have custom fields for competitor name, deal risk, and next step summary. I don’t remember the exact internal field names, but they exist in HubSpot.

Salesperson: Good. What kind of sales calls should we start with?

Customer: Start with discovery and demo follow-up calls. Those are the calls where most CRM updates are missed.

Salesperson: What is the current volume?

Customer: Around 1,200 sales calls per month right now. This may go to 2,500 calls per month after the team expansion.

Salesperson: And what would success look like for you in the first pilot?

Customer: If we can correctly identify next steps, create follow-up tasks, update deal notes, and improve CRM completeness for 20 to 30 deals, that would be a strong pilot.

Salesperson: Are you evaluating any other tools?

Customer: Yes, we are also looking at Gong and Avoma. Gong is strong, but it feels expensive and more analytics-heavy. We need something more execution-focused inside HubSpot.

Salesperson: Understood. Is there a budget range already discussed internally?

Customer: For the pilot, we can approve up to ₹3 lakhs without CFO approval. For annual rollout, we are expecting something around ₹25 to ₹30 lakhs if the pilot works.

Salesperson: Who all need to be involved before final sign-off?

Customer: Meera, our VP Sales, needs to approve the business case. Our RevOps manager, Kunal, will check HubSpot integration. IT security will review data access and retention. Finance will come in only if we go beyond pilot pricing.

Salesperson: What is your desired timeline?

Customer: We want to start the pilot by August 12. If the pilot is successful, we want to decide on annual rollout by September 30.

Salesperson: That’s helpful. Any hard requirement from IT security?

Customer: Yes. We cannot send customer PII to random external systems. We need clarity on where transcripts are stored, whether data is encrypted, and whether we can delete data after the pilot.

Salesperson: We can share our security note. Do you need anything specific in it?

Customer: Please include data retention, encryption, HubSpot permission scopes, and whether your system stores audio files or only transcripts.

Salesperson: Noted. For the pilot, would you prefer us to update CRM directly or first show proposed changes for approval?

Customer: First show proposed changes for approval. I do not want the system directly changing live HubSpot records during the first week.

Salesperson: That’s reasonable. We can show proposed changes like deal field updates, notes, and tasks before applying them.

Customer: Yes, exactly. If it works well, we can automate low-risk updates later, like notes and follow-up tasks.

Salesperson: Which updates would you consider low-risk?

Customer: Creating notes and creating tasks are low-risk. Updating deal amount, close date, and stage should require approval.

Salesperson: Good distinction. Are there any fields that should never be touched?

Customer: Do not touch deal owner, lifecycle stage, source fields, or any system-generated fields. Also, do not change the pipeline or deal stage without approval.

Salesperson: Understood. What should happen when the call mentions something useful but there is no matching CRM field?

Customer: Add it as a note. For example, if a prospect says their board meeting is next Friday or they are unhappy with implementation delays, that should go into notes.

Salesperson: Makes sense. Do you want duplicate task detection?

Customer: Basic duplicate detection is enough. If there is already an open task called “send proposal,” don’t create another one.

Salesperson: Great. What would you like us to send after this call?

Customer: Please send a pilot proposal by tomorrow evening. Include pricing, implementation plan, HubSpot scopes required, and data security details.

Salesperson: Sure. Should we also schedule a technical walkthrough with Kunal?

Customer: Yes. Please schedule a 45-minute technical walkthrough with Kunal and me early next week, preferably Tuesday after 3 PM.

Salesperson: Done. Do you want Meera included in that call?

Customer: Not yet. Let us first validate the technical feasibility. If Kunal is comfortable, we will bring Meera into the commercial discussion.

Salesperson: Understood. Any specific pilot size you have in mind?

Customer: Let’s start with 30 deals and around 100 call transcripts. That should be enough to test quality.

Salesperson: What kind of accuracy would make you comfortable?

Customer: I don’t expect perfection. But for next steps and tasks, I’d want 85% plus accuracy. For deal amount and close date, false updates should be very low because those are sensitive.

Salesperson: So notes and tasks can be semi-automated, but sensitive deal fields need approval.

Customer: Correct.

Salesperson: What happens if this pilot is successful?

Customer: Then we roll it out to the enterprise sales team first, around 45 users. Later, we may expand to customer success and renewals.

Salesperson: Is there any urgency from leadership?

Customer: Yes. Meera wants this solved before Q4 planning. She is frustrated because forecast calls take too long and managers spend half the time asking reps to explain missing CRM updates.

Salesperson: That is a strong use case. Anything else we should know?

Customer: One more thing. We don’t want a dashboard-only tool. If this only gives insights but does not update HubSpot or create action items, it won’t be useful for us.

Salesperson: That’s aligned with our product direction. Our focus is execution, not just insights.

Customer: Good. Then send the proposal tomorrow. Also share two sample outputs: one showing proposed HubSpot deal changes, and one showing task and note creation from a transcript.

Salesperson: Perfect. I’ll send the pilot proposal, implementation plan, security note, and two sample outputs by tomorrow evening. I’ll also propose Tuesday after 3 PM for the technical walkthrough with you and Kunal.

Customer: Great. Once I receive that, I’ll review it and share it internally with Kunal.

Salesperson: Thanks, Rohan. This was very helpful.

Customer: Thanks. Looking forward to the proposal.
"""

async def main():
    db = SessionLocal()
    try:
        service = TranscriptAgentService()
        print("Analyzing transcript via Groq LLM model 'openai/gpt-oss-120b'...")
        result = await service.run_transcript_agent(
            db=db,
            user_id=1,
            provider="hubspot",
            deal_id="333626714873",  # Existing HubSpot Deal ID
            transcript=transcript_text
        )
        print("\n=== PROPOSED CHANGES ===")
        print(json.dumps(result["proposed_changes"], indent=2))
        
        print("\n=== SKIPPED CANDIDATES ===")
        print(json.dumps(result["skipped_candidates"], indent=2))
    except Exception as e:
        print(f"Error during analysis: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
