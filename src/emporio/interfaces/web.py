"""Interface web da Lia em Streamlit (secundária).

Usa a MESMA fachada EmporioAgent da CLI. O agente é referenciado via módulo
(graph.EmporioAgent) para poder ser substituído nos testes com AppTest.
"""

import json

import streamlit as st

from emporio.agent import graph
from emporio.agent.llm import describe
from emporio.bootstrap import ensure_data
from emporio.interfaces.common import setup_logging

st.set_page_config(
    page_title="Empório da Música · Lia",
    page_icon="🎸",
    layout="centered",
)

WELCOME = (
    "Oi! Eu sou a Lia, da Empório da Música. Posso te ajudar a escolher um "
    "instrumento, ver preços e promoções, simular pagamento, acompanhar um "
    "pedido ou tirar dúvidas sobre trocas e entregas."
)

SUGGESTIONS = [
    ("Violões até R$ 1.000", "Quais violões vocês têm até R$ 1000?"),
    ("Promoções de hoje", "Quais promoções estão ativas hoje?"),
    ("Status do meu pedido", "Quero saber o status do meu pedido."),
    ("Como funciona a devolução?", "Como funciona a devolução de um produto?"),
]


@st.cache_resource
def get_agent():
    setup_logging()
    ensure_data()
    return graph.EmporioAgent()


def _init_state() -> None:
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = graph.EmporioAgent.new_thread_id()
    if "turns" not in st.session_state:
        st.session_state.turns = []


def send(text: str) -> None:
    st.session_state.turns.append({"role": "user", "text": text, "tools": []})
    with st.spinner("Lia está digitando..."):
        reply = get_agent().chat(text, st.session_state.thread_id)
    tools = [{"name": c.name, "args": c.args} for c in reply.tool_calls]
    st.session_state.turns.append(
        {"role": "assistant", "text": reply.text, "tools": tools}
    )
    st.rerun()


def _render_sidebar(show_tools_default: bool) -> bool:
    with st.sidebar:
        st.caption(f"Modelo: {describe()}")
        st.caption(f"Conversa: {st.session_state.thread_id}")
        show_tools = st.toggle("Mostrar ferramentas usadas", value=show_tools_default)
        if st.button("Nova conversa"):
            st.session_state.thread_id = graph.EmporioAgent.new_thread_id()
            st.session_state.turns = []
            st.rerun()
        st.caption("Protótipo de desafio técnico. Os dados são fictícios.")
    return show_tools


def main() -> None:
    # Falha cedo e com mensagem amigável se o agente não puder ser criado.
    try:
        get_agent()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    _init_state()

    st.title("Empório da Música")
    st.caption("Sua música começa aqui. · Lia, assistente virtual")

    show_tools = _render_sidebar(show_tools_default=False)

    if not st.session_state.turns:
        with st.chat_message("assistant"):
            st.markdown(WELCOME)
        col1, col2 = st.columns(2)
        for index, (label, message) in enumerate(SUGGESTIONS):
            column = col1 if index % 2 == 0 else col2
            if column.button(label, key=f"sug-{index}", use_container_width=True):
                send(message)

    for turn in st.session_state.turns:
        with st.chat_message(turn["role"]):
            st.markdown(turn["text"])
            if show_tools and turn["role"] == "assistant" and turn["tools"]:
                with st.expander(f"Ferramentas usadas ({len(turn['tools'])})"):
                    for tool in turn["tools"]:
                        st.code(
                            f"{tool['name']}({json.dumps(tool['args'], ensure_ascii=False)})"
                        )

    prompt = st.chat_input("Escreva sua mensagem")
    if prompt:
        send(prompt)


main()
