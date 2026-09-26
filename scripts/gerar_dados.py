"""
Gera os dois arquivos que um gestor de tráfego recebe na vida real, pra
alimentar o painel:

1. data/raw/meta_ads_export.csv — relatório diário por anúncio, no formato
   que o Gerenciador de Anúncios do Meta exporta (colunas em português,
   separador ";" e vírgula decimal, como sai numa conta brasileira).
2. data/raw/pedidos_nuvemshop.csv — pedidos da loja, com as UTMs que a
   página de venda (projeto 4 do portfólio) anexa ao link do checkout.

Os dois são simulados, mas com comportamento de propósito: cada anúncio
tem taxas próprias (CTR, conversão) pra que apareçam casos típicos — um
vencedor claro, um com muito clique e pouca venda, um com poucos dados
pra julgar. E o Meta "enxerga" mais compras do que a loja registra (ver
README: atribuição).

Período fixo (não relativo a hoje): rodar de novo gera exatamente os
mesmos arquivos, e o CI consegue conferir isso.
"""

import csv
import os
import random
from datetime import date, timedelta

FIM = date(2026, 9, 20)
DIAS = 60
INICIO = FIM - timedelta(days=DIAS - 1)
PRECO = 129.90

# campanha: (orçamento diário, dia em que começa)
CAMPANHAS = {
    "[PROSPECÇÃO] Mulheres 25-44 · interesses skincare": (120.0, 0),
    "[REMARKETING] Visitou o site nos últimos 30 dias": (40.0, 0),
    "[TESTE] Lookalike 1% compradoras": (60.0, 30),
}

# (campanha, anúncio, peso no orçamento, CPM, CTR, carrinho/clique,
#  checkout/carrinho, compra/checkout, frequência)
ANUNCIOS = [
    ("[PROSPECÇÃO] Mulheres 25-44 · interesses skincare", "Vídeo depoimento 30s", 0.45, 30.0, 0.015, 0.12, 0.64, 0.76, 1.4),
    ("[PROSPECÇÃO] Mulheres 25-44 · interesses skincare", "Carrossel antes e depois", 0.30, 30.0, 0.012, 0.11, 0.60, 0.70, 1.4),
    ("[PROSPECÇÃO] Mulheres 25-44 · interesses skincare", "Imagem oferta 31% off", 0.25, 30.0, 0.026, 0.05, 0.50, 0.60, 1.4),
    ("[REMARKETING] Visitou o site nos últimos 30 dias", "Vídeo como usar", 0.60, 45.0, 0.018, 0.20, 0.70, 0.80, 3.2),
    ("[REMARKETING] Visitou o site nos últimos 30 dias", "Imagem última chance", 0.40, 45.0, 0.013, 0.15, 0.65, 0.75, 3.2),
    ("[TESTE] Lookalike 1% compradoras", "Vídeo depoimento 30s", 0.92, 26.0, 0.014, 0.12, 0.60, 0.72, 1.3),
    ("[TESTE] Lookalike 1% compradoras", "Imagem kit presente", 0.08, 26.0, 0.010, 0.10, 0.55, 0.70, 1.3),
]

# De cada 100 compras que o Meta atribui a um anúncio, quantas aparecem na
# loja com a UTM daquele anúncio. O resto é compra por visualização (viu o
# anúncio, comprou depois por outro caminho), troca de aparelho ou UTM
# perdida — o Meta conta, a loja não liga ao anúncio.
TAXA_RASTREADA = 0.78
TAXA_CANCELAMENTO = 0.06


def binomial(n: int, p: float) -> int:
    return sum(1 for _ in range(n) if random.random() < p)


def unidades() -> int:
    return random.choices([1, 2, 3], weights=[80, 16, 4])[0]


def slug(texto: str) -> str:
    trocas = str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")
    base = texto.lower().translate(trocas)
    return "-".join("".join(c if c.isalnum() else " " for c in base).split())


def br(valor: float) -> str:
    """Formata como o Excel brasileiro: 1234.5 -> '1234,50'."""
    return f"{valor:.2f}".replace(".", ",")


def simular():
    random.seed(2026)
    linhas_meta, pedidos = [], []
    numero_pedido = 10231
    for d in range(DIAS):
        dia = INICIO + timedelta(days=d)
        for campanha, (orcamento, comeca) in CAMPANHAS.items():
            if d < comeca:
                continue
            gasto_campanha = orcamento * random.uniform(0.9, 1.1)
            anuncios = [a for a in ANUNCIOS if a[0] == campanha]
            pesos = [a[2] * random.uniform(0.85, 1.15) for a in anuncios]
            total_pesos = sum(pesos)
            for anuncio, peso in zip(anuncios, pesos):
                _, nome, _, cpm, ctr, t_carr, t_chk, t_compra, freq = anuncio
                gasto = round(gasto_campanha * peso / total_pesos, 2)
                impressoes = int(gasto / (cpm * random.uniform(0.9, 1.1)) * 1000)
                alcance = int(impressoes / (freq * random.uniform(0.9, 1.1)))
                cliques = binomial(impressoes, ctr)
                carrinhos = binomial(cliques, t_carr)
                checkouts = binomial(carrinhos, t_chk)
                compras = binomial(checkouts, t_compra)
                valor = 0.0
                for _ in range(compras):
                    total = round(unidades() * PRECO, 2)
                    valor += total
                    if random.random() < TAXA_RASTREADA:
                        pedidos.append({
                            "Número do pedido": numero_pedido,
                            "Data": dia.strftime("%d/%m/%Y"),
                            "Status do pagamento": "Cancelado" if random.random() < TAXA_CANCELAMENTO else "Pago",
                            "Total": br(total),
                            "utm_source": random.choices(["instagram", "facebook"], weights=[70, 30])[0],
                            "utm_medium": "paid_social",
                            "utm_campaign": slug(campanha),
                            "utm_content": slug(nome),
                        })
                        numero_pedido += 1
                linhas_meta.append({
                    "Dia": dia.isoformat(),
                    "Nome da campanha": campanha,
                    "Nome do anúncio": nome,
                    "Valor usado (BRL)": br(gasto),
                    "Impressões": impressoes,
                    "Alcance": alcance,
                    "Cliques no link": cliques,
                    "Adições ao carrinho": carrinhos,
                    "Finalizações de compra iniciadas": checkouts,
                    "Compras": compras,
                    "Valor de conversão de compras": br(valor),
                })
    return linhas_meta, pedidos


def salvar(caminho, linhas):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)


def main():
    pasta = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    os.makedirs(pasta, exist_ok=True)
    linhas_meta, pedidos = simular()
    salvar(os.path.join(pasta, "meta_ads_export.csv"), linhas_meta)
    salvar(os.path.join(pasta, "pedidos_nuvemshop.csv"), pedidos)
    print(f"Meta Ads: {len(linhas_meta)} linhas ({INICIO:%d/%m/%Y} a {FIM:%d/%m/%Y})")
    print(f"Nuvemshop: {len(pedidos)} pedidos com UTM de anúncio")


if __name__ == "__main__":
    main()
