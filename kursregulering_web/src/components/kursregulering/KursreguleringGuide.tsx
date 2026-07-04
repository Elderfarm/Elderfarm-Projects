export function KursreguleringGuide() {
  return (
    <details className="group rounded-card border border-border bg-surface shadow-card">
      <summary className="flex cursor-pointer list-none items-center justify-between px-6 py-4 text-sm font-semibold text-foreground">
        📖 Sådan fungerer det — guide og eksempel
        <span className="text-muted transition-transform group-open:rotate-180">⌄</span>
      </summary>
      <div className="space-y-4 px-6 pb-6 text-sm text-muted">
        <div>
          <p className="font-medium text-foreground">De fire linjetyper</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            <li><strong>Primo</strong> — hvad I havde ved årets start (antal og kurs pr. 1. januar)</li>
            <li><strong>Tilgang</strong> — hver gang I køber flere aktier i løbet af året</li>
            <li><strong>Afgang</strong> — hver gang I sælger aktier i løbet af året</li>
            <li><strong>Ultimo</strong> — hvad I har ved årets slutning (antal og kurs pr. 31. december)</li>
          </ul>
        </div>

        <div>
          <p className="font-medium text-foreground">Lagerprincippet, kort fortalt</p>
          <p className="mt-1">
            Primo-kursen er IKKE hvad I oprindeligt betalte for aktierne — det er sidste års
            ultimo-kurs, som allerede er blevet beskattet én gang. I beskattes derfor kun af
            ændringen i værdi i ÅR, ikke af hele gevinsten siden I købte aktierne. Sælger I noget i
            løbet af året, finder vi automatisk ud af (efter FIFO — først ind, først ud), om det
            sælges fra den gamle beholdning eller fra et af årets køb.
          </p>
        </div>

        <div className="rounded-xl bg-muted-subtle p-4">
          <p className="font-medium text-foreground">Eksempel: Novo Nordisk B (tallene fra tabellen nedenfor)</p>
          <ul className="mt-2 space-y-1">
            <li>Primo: 100 stk. à 700 kr. = 70.000 kr. (sidste års værdi)</li>
            <li>Tilgang: 50 stk. à 800 kr. = 40.000 kr. (købt i år)</li>
            <li>
              Afgang: sælger 30 stk. à 900 kr. = 27.000 kr. FIFO tager dem fra primo-beholdningen
              (basis 700 kr./stk.) → <strong>Realiseret gevinst = 27.000 − 30×700 = 6.000 kr.</strong>
            </li>
            <li>
              Ultimo: 120 stk. à 850 kr. = 102.000 kr. Tilbage er 70 stk. fra primo (à 700) + 50
              stk. fra tilgang (à 800) = 89.000 kr. i basis →{" "}
              <strong>Urealiseret gevinst = 102.000 − 89.000 = 13.000 kr.</strong>
            </li>
            <li>Årets samlede kursregulering: 6.000 + 13.000 = <strong>19.000 kr.</strong></li>
          </ul>
        </div>

        <p>
          Brug knappen <strong>&ldquo;Indlæs eksempel&rdquo;</strong> under tabellen for at se disse
          tal indsat, eller <strong>&ldquo;Ryd tabel&rdquo;</strong> for at starte forfra med jeres
          egne data.
        </p>
      </div>
    </details>
  );
}
