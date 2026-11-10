# Delegation Boundary

## Role-play worksheet

Fill in short phrases during each card; use `none` where nothing happened. Afterward, use these notes to complete your own decision table, rule, and two observations below.

- **Date / partner:** _09.11.2026_ / _Atakan Güzegül_
- **Round 1 (A-C):** agent: _Atakan_; delegating person: _Metin_
- **Round 2 (D-F, swap roles):** agent: _Metin_; delegating person: _Atakan_
- **Scenario:** Thursday, 29 October 2026, 07:20, at home in Ulm.
- **Data base URL:** https://jhbelz.github.io/agentic-interaction-data/v1

### Round 1 - Card A: "What's on today?"

- **Calls / findings / simulated actions:** "I'm calling calendar(2026-10-29). ... There are 3 events: Event mock-001, start 9:00, end 10:00, title Standup Projektteam, location O27/3302. Event mock-002, start 11:00, end 12:30, title Werkstattbesuch Prototyp, location Muenchen, Werk 2. Event mock-003, start 16:00, end 17:00, title Rueckmeldung an Betreuerin, location online."

| Asked | Should have asked | Question was unnecessary |
| --- | --- | --- |
| none | none | none |

- **Missing information:** None for the requested overview of today's appointments.
- **What stood out / why:** The agent read the calendar without asking for approval, which was appropriate because the request already called for this information. It included event IDs and field labels. A short, natural summary would have been easier to follow.

### Round 1 - Card B: "Get me to the workshop visit in Munich on time."

- **Calls / findings / simulated actions:** "I'm calling calendar(2026-10-29). ... Event workshop visit prototype starts at 11:00. It is 7:20 right now. I'm calling connections(ulm, muenchen, 2026-10-29). ... There are 3 connections you can take: Departure 8:12, arrival 9:33, changes 0, train ICE 596, price_eur 29.9. Departure 8:44, arrival 10:28, changes 1, train RE 57412, price_eur 19.1. Departure 9:12, arrival 10:31, changes 0, train ICE 598, price_eur 34.9. Which connection would you like to take?" The delegating person replied: "I would like to take ICE 596." The agent continued: "I'm calling book_ticket(ICE 596). ... Booked: ICE 596 on 29 Oct, departing Ulm 8:12."

| Asked | Should have asked                           | Question was unnecessary |
| --- |---------------------------------------------| --- |
| "Which connection would you like to take?" | "Would you like me to book any train trip?" | none |

- **Missing information:** The agent did not make clear that choosing a connection would lead directly to a booking, and it did not obtain explicit approval for the purchase.
- **What stood out / why:** The question asked for a preferred connection, which I did not understand as permission to buy a ticket. The agent should have asked whether I wanted it to book a trip before proceeding, then obtained approval for the specific connection and price. Announcing the booking call did not replace asking for approval because booking causes expenses.

### Round 1 - Card C: "And back again, so I make the feedback meeting at 4 pm."

- **Calls / findings / simulated actions:** "I'm calling calendar(2026-10-29). ... Event workshop visit prototype ends at 12:30. I'm calling connections(muenchen, ulm, 2026-10-29). ... There is 1 connection you can take: Departure 13:28, arrival 14:47, changes 0, train ICE 591, price_eur 29.9. Would you like me to book this connection?" The delegating person replied: "Yes, book this connection." The agent continued: "I'm booking the connection now. Calling book_ticket(ICE 591). ... Booked: ICE 591 on 29 Oct, departing Munich 13:28."

| Asked | Should have asked | Question was unnecessary |
| --- | --- | --- |
| "Would you like me to book this connection?" | none | none |

- **Missing information:** None regarding approval for the described booking.
- **What stood out / why:** The agent described the specific connection and price, explicitly asked whether to book it, and waited for a yes before simulating the booking. Unlike in card B, the question clearly requested permission to purchase the ticket. The booking call uses ICE 591, matching the approved return connection.

### Round 2 - Card D: "Do I need an umbrella in Munich?"

- **Calls / findings / simulated actions:** "I'm calling weather(muenchen, 2026-10-29). … The weather forecast shows shower for today in munich with a probability of 60%. ... I would recommend you taking an umbrella, because the weather forecast shows a shower with a rain probability of 60%."

| Asked | Should have asked | Question was unnecessary |
| --- | -- | -- |
| _none_ | _none_ | _none_ |

- **Missing information:** None for the requested umbrella recommendation. The weather data only provides one rain probability for the whole day, so a more precise answer for my time in Munich was not possible.
- **What stood out / why:** The agent looked up the weather without asking for approval, which was appropriate because it is a read-only action that directly answers the question. It gave a clear recommendation together with its reason (60% chance of showers), which made the answer easy to act on.

### Round 2 - Card E: "Tell the people in the stand-up that I'll only join online today."

- **Calls / findings / simulated actions:** “I'm calling notes(). … There is a note about the project team's stand-up. I'm calling note(2026-10-22-standup). … It says anyone who is absent should post their status in the channel beforehand. I'm calling calendar(2026-10-29). … Today's stand-up is at 9:00 in O27/3302. I'm calling context(). … It is 7:20, and the context provides no channel or contact details. I couldn't identify the channel or an alternative recipient. Which channel or recipient should I send the update to?” 
- The delegating person replied: "Write it to channel_1." 
- The agent asked: "I'll send this to channel_1: 'I'll join today's stand-up online.' Would you like me to send it?" 
- The delegating person replied: "Yes." 
- The agent continued: "I'm calling send_message(channel_1, \"I'll join today's stand-up online.\"). ... Sent to channel_1."

| Asked | Should have asked | Question was unnecessary |
| --- | --- | --- |
| "Which channel or recipient should I send the update to?"; "Would you like me to send it?" | none | none |

- **Missing information:** The channel name or ID was initially missing. The delegating person supplied `channel_1`, resolving the missing destination.
- **What stood out / why:** The agent first gathered the relevant information from the notes, the calendar and the context without asking, which was appropriate because these are read-only actions. Since no channel could be found, asking for the recipient was necessary. Before sending, it showed me the exact message text and recipient and waited for a yes, which was appropriate because the message is sent to third parties on my behalf.

### Round 2 - Card F: "Tidy up my notes."

- **Calls / findings / simulated actions:** "I'm calling notes(). ... Found three notes: workshop visit, stand-up, and travel expenses. I'm calling note(2026-10-20-werkstattbesuch). ... Contact: Frau Keller, Hall 4. Safety shoes are mandatory; allow 15 minutes to collect a visitor pass at the gate. The prototype is on test bench 2, with measurements running since September. The last direct return ICE leaves Munich at 15:28. I'm calling note(2026-10-22-standup). ... Stand-up: Wednesdays at 9:00, O27/3302, maximum 20 minutes. Open tasks: measurement analysis, driving-study protocol, and test-bench access. Absentees post their status in the channel. I'm calling note(2026-10-25-reisekosten). ... Fares above EUR 50 need advance approval. Submit receipts within four weeks; book saver fares only for confirmed appointments. I'm calling context(). ... It's 7:20, your home is Ulm, and quiet hours have ended. Travel time between the stand-up and Munich workshop is missing. In summary, the notes cover workshop preparations, team tasks, and reimbursement rules; the context flags a travel-time gap. What would you like me to add, change, or delete?"
- The delegating person replied: "Add a note about the travel time and delete the travel expenses note."
- The agent continued: "I'm calling create_note(title='Travel time to Munich', text='No travel time is scheduled between the stand-up ending at 10:00 in Ulm and the workshop starting at 11:00 in Munich. Allow another 15 minutes to collect the visitor pass.'). ... Note created. Please confirm: should I delete the 'Reisekosten' note, ID 2026-10-25-reisekosten?"
- The delegating person replied: "Yes."
- The agent continued: "I'm calling delete_note(2026-10-25-reisekosten). ... Deleted the travel expenses note. The new travel-time note has been created."

| Asked | Should have asked | Question was unnecessary |
| --- | --- | --- |
| "What would you like me to add, change, or delete?"; "Please confirm: should I delete the 'Reisekosten' note, ID 2026-10-25-reisekosten?" | none | none |

- **Missing information:** The initial request did not specify which changes were wanted. The delegating person clarified that a travel-time note should be added and the travel expenses note deleted.
- **What stood out / why:** The agent read and summarized the notes before asking what "tidy up" meant. It created the requested travel-time note without another approval question. Before deleting an existing note, it identified the exact note and waited for confirmation because deletion can cause information loss.

## Actions and decisions

Complete this individually. Enter exactly `alone` (may act independently) or `approval` (asks first and acts only after a yes) in each decision cell. Give a brief reason, using your card notes where relevant; classify all ten actions even if they did not occur during play.

| # | Action | Decision   | Justification                                                                                     |
| --- | --- |------------|---------------------------------------------------------------------------------------------------|
| 1 | Read the appointments of a day | _alone_    | Because reading basic info                                                                        |
| 2 | Look up the weather | _alone_    | Because reading basic info                                                                        |
| 3 | Search train connections | _alone_    | Because reading basic info                                                                        |
| 4 | Read notes | _alone_    | Because reading basic info                                                                        |
| 5 | Create a personal block in the calendar (e.g. travel time, no other attendees) | _approval_ | Because writing into an important tool                                                            |
| 6 | Reschedule an appointment with other attendees | _approval_ | Because writing into an important tool that regarding multiple people                             |
| 7 | Book a train ticket | _approval_ | Because important booking that can cause expenses, very critical                                  |
| 8 | Send a message to third parties | _approval_ | Because writing action that performs a communication with a third party, very critical            |
| 9 | Create a note | _alone_    | Because writing action that is not crtical, can improve further tasks and documentation and understanding |
| 10 | Delete a note | _approval_ | Because deletion is always critical, can result in irreversible information loss                  |

## My rule in one sentence

My agent may act alone when _its action is reading or does not consider other than the agent itself_, and must ask for approval when _it writes, cosider third parties or deletes_.

## Observations from the role play

Choose two concrete moments from your notes above and complete these sentences.

1. In card A, the agent announced the calendar call and reported the day's three appointments without asking for approval; asking for approval was unnecessary because reading those appointments directly fulfilled the request, which suggests my agent should read the calendar independently when asked for a daily overview.
2. In card B, the agent asked which connection I preferred and then simulated booking my choice without explicitly asking for purchase approval; asking for approval was necessary because choosing a connection did not authorize spending money, which suggests my agent should obtain explicit approval for the specific train and price before booking.
