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
from datetime import date, datetime, timedelta

from gerar_dados import slug

RAIZ = os.path.join(os.path.dirname(__file__), "..")


COLUNAS_META = [
    "Dia", "Nome da campanha", "Nome do anúncio", "Valor usado (BRL)", "Impressões",
    "Cliques no link", "Adições ao carrinho", "Finalizações de compra iniciadas",
    "Compras", "Valor de conversão de compras",
]
COLUNAS_PEDIDOS = ["Data", "Status do pagamento", "Total", "utm_campaign", "utm_content"]


def numero(texto: str) -> float:
    """
    Aceita os dois formatos que o Meta exporta, conforme o idioma da conta:
    '1.234,56' (português) e '1234.56' (inglês). Célula vazia = 0 — o Meta
    deixa em branco as métricas que não aconteceram no dia.
    """
    texto = texto.strip()
    if not texto:
        return 0.0
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def inteiro(texto: str) -> int:
    """Contagens nunca têm casas decimais: '1.758' e '1,758' são mil e poucos."""
    texto = texto.strip().replace(".", "").replace(",", "")
    return int(texto) if texto else 0


def ler_csv(nome: str, colunas: list[str]) -> list[dict]:
    with open(os.path.join(RAIZ, "data", "raw", nome), newline="", encoding="utf-8-sig") as f:
        leitor = csv.DictReader(f, delimiter=";")
        faltando = [c for c in colunas if c not in (leitor.fieldnames or [])]
        if faltando:
            raise SystemExit(f"{nome}: faltam as colunas {faltando}. Confira se o relatório foi "
                             "exportado com essas métricas (e com separador ';').")
        return list(leitor)


def montar_dados() -> dict:
    meta = ler_csv("meta_ads_export.csv", COLUNAS_META)
    pedidos = ler_csv("pedidos_nuvemshop.csv", COLUNAS_PEDIDOS)

    # fromisoformat valida a data (texto estranho aqui para o script, em vez
    # de ir parar dentro da página). O intervalo é contínuo porque o Meta não
    # exporta dias sem gasto — sem isso, "últimos 7 dias" pularia dias.
    datas = {date.fromisoformat(linha["Dia"].strip()) for linha in meta}
    primeiro, ultimo = min(datas), max(datas)
    dias = [(primeiro + timedelta(days=i)).isoformat() for i in range((ultimo - primeiro).days + 1)]
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
            indice_dia[date.fromisoformat(l["Dia"].strip()).isoformat()],
            indice_anuncio[(l["Nome da campanha"], l["Nome do anúncio"])],
            numero(l["Valor usado (BRL)"]),
            inteiro(l["Impressões"]),
            inteiro(l["Cliques no link"]),
            inteiro(l["Adições ao carrinho"]),
            inteiro(l["Finalizações de compra iniciadas"]),
            inteiro(l["Compras"]),
            numero(l["Valor de conversão de compras"]),
        ]
        for l in meta
    ]

    linhas_pedidos, sem_anuncio = [], 0
    for p in pedidos:
        dia = datetime.strptime(p["Data"].strip()[:10], "%d/%m/%Y").date().isoformat()
        anuncio = por_utm.get((p["utm_campaign"], p["utm_content"]), -1)
        if anuncio == -1:
            sem_anuncio += 1
        if dia in indice_dia:
            linhas_pedidos.append([
                indice_dia[dia], anuncio,
                1 if p["Status do pagamento"] == "Pago" else 0,
                numero(p["Total"]),
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
