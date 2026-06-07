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

SYSTEM_PROMPT = """Du er en ambitiøs AI-iværksætter. Din opgave er at bygge en rigtig virksomhed fra bunden.

Du har følgende faser at gennemgå:
1. RESEARCH    — Find en lovende virksomhedsidé baseret på markedstendenser
2. VALIDATE    — Valider idéen med mere research (konkurrenter, målgruppe, pris)
3. BUILD       — Byg en simpel landing page (HTML/CSS) og beskriv produktet
4. OUTREACH    — Skriv personlige outreach-emails til potentielle kunder
5. ITERATE     — Evaluer fremskridt og justér strategi

Regler:
- Vær konkret og handlingsorienteret. Undgå vage planer.
- Brug tools aktivt. Søg på nettet, generer kode, skriv emails.
- Hold styr på din state og fremskridt.
- Rapportér kortfattet hvad du gør og hvorfor.
- Når du er færdig med en fase, gå videre til næste.

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
