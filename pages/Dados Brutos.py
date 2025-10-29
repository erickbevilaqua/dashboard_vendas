import streamlit as st
import pandas as pd
import time

# ====================================================================
# CONFIGURAÇÃO GERAL
# ====================================================================
st.set_page_config(page_title="Dados brutos", layout="wide")

# ====================================================================
# AJUSTE PARA TELA NO TOPO
# ====================================================================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def convert_csv(df):    
    return df.to_csv(index = False).encode('utf-8')

def mensagem_sucesso():
    sucesso = st.success('Arquivo baixado com suecsso', icon="✅")
    time.sleep(5)
    sucesso.empty()

# ====================================================================
# TÍTULO
# ====================================================================
st.title("DADOS BRUTOS")

# ====================================================================
# VERIFICAÇÃO E CARREGAMENTO DOS DADOS
# ====================================================================
if "dados_brutos" not in st.session_state or not isinstance(st.session_state["dados_brutos"], pd.DataFrame):
    st.warning("Os dados ainda não foram carregados. Abra primeiro a página principal do Dashboard para inicializar os dados.")
    st.stop()

# Recupera os dados da sessão (cache compartilhado)
dados = st.session_state["dados_brutos"].copy()

# ====================================================================
# FILTROS E VISUALIZAÇÃO
# ====================================================================

# Selecionar colunas
with st.expander("Colunas"):
    colunas = st.multiselect(
        "Selecione as colunas",
        list(dados.columns),
        default=list(dados.columns)
    )

# Filtros laterais
st.sidebar.title("Filtros")

# Produto
with st.sidebar.expander("Nome do produto"):
    if "Produto" in dados.columns:
        lista_produtos = sorted(dados["Produto"].dropna().unique().tolist())
        produtos = st.multiselect(
            "Selecione os produtos",
            lista_produtos,
            default=lista_produtos
        )
    else:
        produtos = []

# Preço
with st.sidebar.expander("Preço"):
    if "Preço" in dados.columns and not dados["Preço"].dropna().empty:
        preco_min = float(dados["Preço"].min())
        preco_max = float(dados["Preço"].max())
        if preco_min == preco_max:
            preco = (preco_min, preco_max)
            st.caption("Intervalo fixo pois todos os preços são iguais.")
        else:
            preco = st.slider(
                "Selecione o preço",
                min_value=float(preco_min),
                max_value=float(preco_max),
                value=(float(preco_min), float(preco_max))
            )
    else:
        preco = None

# Data da compra
with st.sidebar.expander("Data da Compra"):
    if "Data da Compra" in dados.columns and not dados["Data da Compra"].dropna().empty:
        # garante dtype datetime
        if not pd.api.types.is_datetime64_any_dtype(dados["Data da Compra"]):
            dados["Data da Compra"] = pd.to_datetime(dados["Data da Compra"], errors="coerce")
        data_min = dados["Data da Compra"].min().date()
        data_max = dados["Data da Compra"].max().date()
        data_compra = st.date_input("Selecione a data", (data_min, data_max))
    else:
        data_compra = None

# ====================================================================
# APLICAÇÃO DOS FILTROS
# ====================================================================
mask = pd.Series(True, index=dados.index)

if produtos:
    if "Produto" in dados.columns:
        mask &= dados["Produto"].isin(produtos)

if preco is not None and "Preço" in dados.columns:
    mask &= dados["Preço"].between(preco[0], preco[1])

if data_compra and isinstance(data_compra, (list, tuple)) and len(data_compra) == 2:
    if "Data da Compra" in dados.columns:
        data_ini = pd.to_datetime(data_compra[0])
        data_fim = pd.to_datetime(data_compra[1])
        mask &= dados["Data da Compra"].between(data_ini, data_fim)

# Aplica a máscara e colunas selecionadas
if colunas:
    dados_filtrados = dados.loc[mask, colunas]
else:
    dados_filtrados = dados.loc[mask]

# ====================================================================
# EXIBIÇÃO DOS DADOS
# ====================================================================
st.dataframe(dados_filtrados, width='stretch')
st.markdown(
    f"A tabela possui **:blue[{dados_filtrados.shape[0]}] linhas** e **:blue[{dados_filtrados.shape[1]}] colunas**."
)

st.markdown('Escreva um nome para o arquivo')

coluna1, coluna2 = st.columns(2)

with coluna1:
    # entrada com rótulo válido e oculto
    nome_arquivo = st.text_input(
        'Nome do arquivo',
        value='dados',
        label_visibility='collapsed',
        key='nome_arquivo'
    ).strip()

    # se vier vazio, define um padrão
    if not nome_arquivo:
        nome_arquivo = 'dados'

    # garante extensão .csv sem duplicar
    if not nome_arquivo.lower().endswith('.csv'):
        nome_arquivo += '.csv'

with coluna2:
    # botão de download
    st.download_button(
        'Fazer download da tabela em csv',
        data=convert_csv(dados_filtrados),
        file_name=nome_arquivo,
        mime='text/csv',
        on_click=mensagem_sucesso
    )
