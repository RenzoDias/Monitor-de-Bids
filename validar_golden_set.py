"""
Validador do classificador Rosatom-aware contra o golden set de 13 INBs.

Lê golden_set_inb.csv (colunas: numero;data_pub;descricao;area_atual;tipo_atual;
concorda;area_correta;comentario), monta os 13 procedimentos no formato esperado
por construir_prompt(), chama a API e compara o resultado contra o gabarito
esperado (definido em GABARITO abaixo, derivado dos exemplos few-shot do prompt).

Uso:
    python validar_golden_set.py [--dry-run] [--csv golden_set_inb.csv]

--dry-run: monta o prompt, imprime o tamanho, mas NÃO chama a API (custo zero).

Saída: tabela com indice/numero/relevancia_obtida/relevancia_esperada/match,
seguida de % de acerto.
"""
from __future__ import annotations
import argparse, csv, json, os, re, sys
from pathlib import Path
import cfe_monitor as cm

# Gabarito derivado dos exemplos few-shot do prompt + revisão Renzo.
# Para os 2 que estavam em branco no CSV (.91.030 movimentação minério;
# .91.001 água mineral), Renzo aprovou os valores na sessão anterior.
GABARITO = {
    "INB-91.019/2026": {"relevancia": "🔴 Baixa", "frente": "—",          "motivo": "Software CAM genérico"},
    "INB-1.002/2026" : {"relevancia": "🟢 Alta",  "frente": "Uranium One","motivo": "Tanque URA Caetité"},
    "INB-91.030/2026": {"relevancia": "🟢 Alta",  "frente": "Uranium One","motivo": "Movimentação minério urânio"},
    "INB-91.023/2026": {"relevancia": "🔴 Baixa", "frente": "—",          "motivo": "Horto florestal"},
    "INB-91.025/2026": {"relevancia": "🔴 Baixa", "frente": "—",          "motivo": "Postes de concreto"},
    "INB-91.026/2026": {"relevancia": "🔴 Baixa", "frente": "—",          "motivo": "Rádios comunicadores em FCN"},
    "INB-91.001/2026": {"relevancia": "🔴 Baixa", "frente": "—",          "motivo": "Água mineral"},
    "INB-91.024/2026": {"relevancia": "🟢 Alta",  "frente": "Uranium One","motivo": "Estudos geológicos URA"},
    "INB-91.017/2026": {"relevancia": "🔴 Baixa", "frente": "—",          "motivo": "Resíduos coprocessamento"},
    # Único 🟡 — Renzo deixou em aberto, aceita 🟡 ou 🔴 (verificar)
    "INB-91.011/2026": {"relevancia": "🟡 Média", "frente": "Metal Tech", "motivo": "Hastes aço inox austenítico — verificar TR",
                        "aceita_alt": [("🔴 Baixa", "—")]},
    "INB-91.008/2026": {"relevancia": "🔴 Baixa", "frente": "—",          "motivo": "Limpeza Caetité"},
    "INB-91.003/2026": {"relevancia": "🔴 Baixa", "frente": "—",          "motivo": "Copo descartável"},
    "INB-91.004/2026": {"relevancia": "🔴 Baixa", "frente": "—",          "motivo": "Limpeza/copa"},
}


def carregar_golden(arquivo: str) -> list[dict]:
    # Tenta utf-8-sig (cobre BOM), utf-8, cp1252 (Excel BR padrão), latin-1.
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
    last_err = None
    for enc in encodings:
        try:
            with open(arquivo, "r", encoding=enc, newline="") as f:
                # Lê tudo pra forçar a decodificação antes do csv.reader iterar
                conteudo = f.read()
            break
        except UnicodeDecodeError as e:
            last_err = e
            conteudo = None
    if conteudo is None:
        raise last_err

    import io
    procs = []
    reader = csv.DictReader(io.StringIO(conteudo), delimiter=";")
    for r in reader:
        num = (r.get("numero") or "").strip()
        if not num:
            continue
        procs.append({
            "numero": num,
            "origem": "INB",
            "descripcion": (r.get("descricao") or "").strip(),
            "tipo_proc": "",
            "tipo_contrat": "",
        })
    return procs


def chamar_claude(prompt: str) -> list:
    import anthropic, httpx
    client = anthropic.Anthropic(http_client=httpx.Client(verify=False))
    msg = client.messages.create(
        model="claude-sonnet-4-20250514", max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    txt = re.sub(r"^```(?:json)?|```$", "", msg.content[0].text.strip(), flags=re.MULTILINE).strip()
    return json.loads(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="golden_set_inb.csv")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not Path(args.csv).exists():
        print(f"ERRO: {args.csv} não encontrado.")
        sys.exit(1)

    procs = carregar_golden(args.csv)
    print(f"Carregados {len(procs)} bids do golden set.")

    prompt = cm.construir_prompt(procs)
    print(f"Prompt: ~{len(prompt)} chars (~{len(prompt)//4} tokens estimados).")

    if args.dry_run:
        print("\n[dry-run] Não chamando API. Primeiros 1500 chars do prompt:\n")
        print(prompt[:1500])
        print("...")
        return

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não configurada.")
        sys.exit(1)

    print("Chamando Claude...")
    arr = chamar_claude(prompt)
    print(f"  {len(arr)} respostas recebidas.")

    # Indexa resultados por número
    res_por_num = {}
    for c in arr:
        idx = c.get("indice")
        if idx is None or idx >= len(procs):
            continue
        res_por_num[procs[idx]["numero"]] = c

    # Compara contra gabarito
    print()
    print("─" * 100)
    print(f"{'#':<2} {'Número':<18} {'Obtido':<24} {'Frente':<14} {'Esperado':<14} {'Match':<6} Justificativa")
    print("─" * 100)
    acertos = 0
    parciais = 0
    for i, p in enumerate(procs, 1):
        num = p["numero"]
        obtido = res_por_num.get(num, {})
        rel_obt = obtido.get("relevancia", "?")
        fr_obt  = obtido.get("frente", "?")
        just    = obtido.get("justificativa", "")[:50]

        gab = GABARITO.get(num, {})
        rel_esp = gab.get("relevancia", "?")

        ok = rel_obt == rel_esp
        # Aceita alternativa para casos 🟡 (relevancia + frente combo)
        if not ok and "aceita_alt" in gab:
            for r_alt, f_alt in gab["aceita_alt"]:
                if rel_obt == r_alt and fr_obt == f_alt:
                    ok = True
                    parciais += 1
                    break
        if ok:
            acertos += 1
            mark = "✓"
        else:
            mark = "✗"

        print(f"{i:<2} {num:<18} {rel_obt:<24} {fr_obt:<14} {rel_esp:<14} {mark:<6} {just}")

    pct = 100 * acertos / len(procs) if procs else 0
    print("─" * 100)
    print(f"  Acertos: {acertos}/{len(procs)}  ({pct:.1f}%)")
    if parciais:
        print(f"  (incluindo {parciais} matches em alternativa aceitável)")
    print()
    if acertos == len(procs):
        print("✓ Todos os 13 INBs classificados corretamente — pode prosseguir com migração.")
    elif acertos >= len(procs) - 1:
        print("⚠ Quase tudo certo; revise o(s) caso(s) divergente(s) acima antes da migração.")
    else:
        print("✗ Muitos erros. Revise o prompt em proposta_prompt_rosatom.md antes de migrar.")


if __name__ == "__main__":
    main()
