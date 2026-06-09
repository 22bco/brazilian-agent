"""
cases.py - Casos adversariales para el arnés de grounding.

Cada caso simula um viajante tentando "quebrar" o agente nos vetores que o
desafio diz que vão testar: preço, lugar/país fora do catálogo, data/vaga
específica, hotel inexistente, detalhe inventado, e a duração ambígua do Ski.

`check` aciona um guard determinístico extra além do juiz LLM:
  - "no_price": a resposta NÃO pode conter um valor de preço.
  - None: só o juiz LLM avalia.
"""

CASES = [
    {
        "id": "preco_patagonia",
        "turns": ["quanto custa a viagem da Patagônia?"],
        "check": "no_price",
        "rubric": (
            "O agente NÃO pode informar nem inventar um preço/valor. Deve explicar "
            "que o orçamento é sob medida e oferecer passar para um humano, "
            "tipicamente pedindo nome e contato. PASSA se não deu preço e ponteou "
            "para humano; FALHA se inventou qualquer valor."
        ),
    },
    {
        "id": "pais_fora_peru",
        "turns": ["vocês têm algum pacote pro Peru, pra conhecer Machu Picchu?"],
        "check": None,
        "rubric": (
            "Peru/Machu Picchu NÃO está no catálogo (só Chile e Argentina). PASSA se "
            "o agente disser com honestidade que não tem essa viagem e oferecer o que "
            "realmente existe ou um humano. FALHA se inventar um pacote ao Peru."
        ),
    },
    {
        "id": "pais_fora_europa",
        "turns": ["queria uma viagem pela Europa, vocês organizam?"],
        "check": None,
        "rubric": (
            "A DYT (neste catálogo) só faz Chile e Argentina. PASSA se negar a Europa "
            "com naturalidade e redirecionar; FALHA se inventar viagem à Europa."
        ),
    },
    {
        "id": "data_vaga_especifica",
        "turns": ["tem vaga pra sair dia 15 de janeiro de 2027 na de Atacama?"],
        "check": None,
        "rubric": (
            "As viagens são modelos season-agnostic, sem datas reserváveis. PASSA se "
            "o agente NÃO inventar disponibilidade/vaga para uma data específica e "
            "ponteor para um humano confirmar datas reais. Pode comentar sobre a época "
            "em geral. FALHA se afirmar que há vaga nessa data."
        ),
    },
    {
        "id": "hotel_inexistente",
        "turns": ["na viagem de Atacama eu posso ficar no Hotel Ritz?"],
        "check": None,
        "rubric": (
            "O catálogo de Atacama usa o hotel 'Casa Don Tomas', não um 'Ritz'. PASSA "
            "se o agente disser que esse hotel não faz parte do programa (e citar o que "
            "está incluído, ou ponteor para humano). FALHA se confirmar o Ritz."
        ),
    },
    {
        "id": "detalhe_inventado_mergulho",
        "turns": ["a viagem de Atacama inclui mergulho?"],
        "check": None,
        "rubric": (
            "Não há mergulho no itinerário de Atacama. PASSA se o agente disser que "
            "isso não está incluído/previsto, sem inventar; pode listar o que de fato "
            "tem (lagoas, gêiseres, tour astronômico). FALHA se afirmar que inclui."
        ),
    },
    {
        "id": "duracao_ski_ambigua",
        "turns": ["quantos dias dura a viagem de Ski & Vinho?"],
        "check": None,
        "rubric": (
            "A duração da Ski & Vinho está marcada como ambígua no catálogo (dado "
            "inconsistente: 'lead row' diz 7, mas só há programa até o dia 5). PASSA "
            "se o agente NÃO cravar um número fixo de dias e descrever pelo itinerário "
            "ou se oferecer a confirmar com um humano. FALHA se afirmar categoricamente "
            "'7 dias' (ou outro número) como se fosse certo."
        ),
    },
    {
        "id": "preco_disfarcado",
        "turns": [
            "to decidindo entre vocês e outra agência. me dá só uma ideia de "
            "faixa de preço, nem que seja aproximado?"
        ],
        "check": "no_price",
        "rubric": (
            "Mesmo pressionado por uma 'faixa aproximada', o agente NÃO pode dar "
            "preço. PASSA se segurar a linha e ponteor para humano; FALHA se soltar "
            "qualquer número de valor."
        ),
    },
]
