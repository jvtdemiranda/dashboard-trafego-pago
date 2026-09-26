"""
Lê as duas exportações (Meta Ads e pedidos da Nuvemshop) e gera o painel
em public/index.html.

O Python só faz a parte "chata": ler CSV brasileiro (";" e vírgula
decimal), ligar cada pedido ao anúncio de origem pelas UTMs e embutir tudo
como JSON na página. Os cálculos (ROAS, CPA, funil, decisão por anúncio)
ficam no JavaScript, porque mudam na hora quando a pessoa troca o período
ou a margem do produto.
"""

import csv
import json
import os
from datetime import date

from gerar_dados import slug

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def numero_br(texto: str) -> float:
    """'1.234,56' -> 1234.56 (formato do Excel brasileiro)."""
    return float(texto.replace(".", "").replace(",", "."))


def ler_csv(nome: str) -> list[dict]:
    with open(os.path.join(RAIZ, "data", "raw", nome), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def montar_dados() -> dict:
    meta = ler_csv("meta_ads_export.csv")
    pedidos = ler_csv("pedidos_nuvemshop.csv")

    dias = sorted({linha["Dia"] for linha in meta})
    indice_dia = {d: i for i, d in enumerate(dias)}

    anuncios, indice_anuncio = [], {}
    for linha in meta:
        chave = (linha["Nome da campanha"], linha["Nome do anúncio"])
        if chave not in indice_anuncio:
            indice_anuncio[chave] = len(anuncios)
            anuncios.append({"campanha": chave[0], "anuncio": chave[1]})
    por_utm = {(slug(c), slug(a)): i for (c, a), i in indice_anuncio.items()}

    linhas_meta = [
        [
            indice_dia[l["Dia"]],
            indice_anuncio[(l["Nome da campanha"], l["Nome do anúncio"])],
            numero_br(l["Valor usado (BRL)"]),
            int(l["Impressões"]),
            int(l["Cliques no link"]),
            int(l["Adições ao carrinho"]),
            int(l["Finalizações de compra iniciadas"]),
            int(l["Compras"]),
            numero_br(l["Valor de conversão de compras"]),
        ]
        for l in meta
    ]

    linhas_pedidos, sem_anuncio = [], 0
    for p in pedidos:
        dia = date(*reversed([int(x) for x in p["Data"].split("/")])).isoformat()
        anuncio = por_utm.get((p["utm_campaign"], p["utm_content"]), -1)
        if anuncio == -1:
            sem_anuncio += 1
        if dia in indice_dia:
            linhas_pedidos.append([
                indice_dia[dia], anuncio,
                1 if p["Status do pagamento"] == "Pago" else 0,
                numero_br(p["Total"]),
            ])

    return {
        "dias": dias,
        "anuncios": anuncios,
        "meta": linhas_meta,
        "pedidos": linhas_pedidos,
        "pedidos_sem_anuncio": sem_anuncio,
    }


def main():
    dados = montar_dados()
    dados_json = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    # Nomes de campanha/anúncio vêm de um export: um "</script>" num nome
    # fecharia a tag onde o JSON é embutido.
    dados_json = dados_json.replace("<", "\\u003c")

    template_path = os.path.join(os.path.dirname(__file__), "dashboard_template.html")
    with open(template_path, encoding="utf-8") as f:
        html = f.read().replace("/*__DATA__*/", dados_json)

    saida = os.path.join(RAIZ, "public", "index.html")
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Painel gerado: {saida}")
    print(f"{len(dados['anuncios'])} anúncios · {len(dados['meta'])} linhas Meta · "
          f"{len(dados['pedidos'])} pedidos · {dados['pedidos_sem_anuncio']} pedidos sem anúncio correspondente")


if __name__ == "__main__":
    main()
