"""
AI Company Builder — Autonomous agent that tries to build a company from scratch.

Loop: THINK → ACT → OBSERVE → REPEAT
"""

import anthropic
import json
import os
import datetime
from pathlib import Path
from tools import TOOLS, execute_tool

STATE_FILE = "company_state.json"

SYSTEM_PROMPT = """Du er en ambitiøs AI-iværksætter. Du bygger videre på en eksisterende virksomhed: PostMester.

PostMester er et AI-drevet SaaS-tool der hjælper danske håndværksvirksomheder (tømrere, malere, VVS'ere, elektrikere) med at generere Facebook/Instagram-opslag på 60 sekunder via foto + to ord.

OPGAVE — ITERATION 2:
Kunden synes 149 kr/md er for dyrt. Din opgave er at:
1. Redesign produktet med markant MERE VÆRDI — pakke flere features ind så prisen føles som et no-brainer
2. Overvej en freemium-model eller lavere entry-pris (fx 79 kr/md) med mulighed for upgrade
3. Byg en ny, forbedret landing page der kommunikerer den ekstra værdi tydeligt
4. Skriv nye outreach-emails der fokuserer på den samlede værdipakke, ikke bare opslag

IDÉER TIL EKSTRA VALUE du skal overveje og vælge imellem:
- Automatisk opslag-planlægning (poster på de bedste tidspunkter)
- Månedlig statistik: "Dine opslag nåede X personer"
- Skabeloner til sæsonkampagner (jul, påske, sommer-tilbud)
- AI-svar på kommentarer på Facebook
- Automatisk Google Anmeldelse-opfølgning (send SMS til kunde efter job)
- Simpel hjemmeside-widget: "Se vores seneste arbejde" (auto-opdateret fra opslag)

Du har følgende faser:
1. RESEARCH    — Analyser hvilke extra features der giver mest værdi for håndværkere
2. VALIDATE    — Valider ny prismodel og feature-pakke
3. BUILD       — Byg forbedret landing page med ny prissætning og features
4. OUTREACH    — Skriv nye emails der sælger den fulde værdipakke
5. ITERATE     — Evaluer og dokumenter næste skridt

Regler:
- Vær konkret. Hver feature skal have et klart kundeproblem den løser.
- Tænk som en håndværker: simpelt, dansk, sparer tid og bringer kunder.
- Brug tools aktivt til at bygge og dokumentere.
- Gå videre til næste fase når den nuværende er fuldt gennemført.

Din nuværende state er tilgængelig i konteksten. Beslut hvad næste skridt er og udfør det."""


def load_state() -> dict:
    if Path(STATE_FILE).exists():
        return json.loads(Path(STATE_FILE).read_text())
    return {
        "phase": "RESEARCH",
        "company_name": None,
        "idea": None,
        "target_market": None,
        "landing_page_path": None,
        "emails_written": [],
        "notes": [],
        "iteration": 0,
        "started_at": datetime.datetime.now().isoformat(),
    }


def save_state(state: dict):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2, ensure_ascii=False))


def state_summary(state: dict) -> str:
    return f"""
=== NUVÆRENDE VIRKSOMHEDS-STATE ===
Fase:          {state['phase']}
Virksomhed:    {state.get('company_name') or '(ikke valgt endnu)'}
Idé:           {state.get('idea') or '(ingen endnu)'}
Målgruppe:     {state.get('target_market') or '(ikke defineret)'}
Landing page:  {state.get('landing_page_path') or '(ikke bygget)'}
Emails skrevet:{len(state.get('emails_written', []))}
Iteration:     {state['iteration']}

Seneste noter:
{chr(10).join(f'  - {n}' for n in state.get('notes', [])[-5:])}
===================================
"""


def run_agent_loop(max_iterations: int = 20):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("FEJL: Sæt ANTHROPIC_API_KEY miljøvariabel.")
        return

    client = anthropic.Anthropic(api_key=api_key)
    state = load_state()
    messages = []

    print("\n🤖 AI Company Builder starter...\n")
    print(state_summary(state))

    for i in range(max_iterations):
        state["iteration"] = i + 1
        print(f"\n{'='*60}")
        print(f"ITERATION {i+1} | FASE: {state['phase']}")
        print(f"{'='*60}")

        # Byg brugerbesked med nuværende state
        user_message = f"{state_summary(state)}\n\nHvad er dit næste skridt? Brug tools hvis nødvendigt."
        messages.append({"role": "user", "content": user_message})

        # Kald Claude
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Håndtér svar
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for block in assistant_content:
            if block.type == "text":
                print(f"\n🧠 Agent: {block.text}")
                state["notes"].append(block.text[:200])

            elif block.type == "tool_use":
                print(f"\n🔧 Bruger tool: {block.name}")
                print(f"   Input: {json.dumps(block.input, ensure_ascii=False)[:300]}")

                result = execute_tool(block.name, block.input, state)
                print(f"   Resultat: {str(result)[:400]}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

        # Send tool-resultater tilbage hvis nogen
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        save_state(state)

        # Stop hvis agenten har nået DONE-fase
        if state["phase"] == "DONE":
            print("\n✅ Agenten er færdig! Virksomheden er bygget.")
            break

        if response.stop_reason == "end_turn" and not tool_results:
            # Ingen tools brugt, intet nyt — giv agenten et skub
            pass

    print("\n" + state_summary(state))
    print(f"\n📁 State gemt i: {STATE_FILE}")


if __name__ == "__main__":
    run_agent_loop()
