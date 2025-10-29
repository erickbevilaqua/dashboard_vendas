import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import numpy as np
import pyarrow

# ====================================================================
# CONFIG PLOTLY (apenas chaves válidas do config)
# ====================================================================
CONFIG_PLOTLY = {
    "displayModeBar": True,
    "displaylogo": False
}

def show_chart(fig):
    # NENHUM outro kwargs aqui, só config
    st.plotly_chart(fig, config=CONFIG_PLOTLY)

# ====================================================================
# CONFIGURAÇÃO GERAL
# ====================================================================
st.set_page_config(
    page_title='DASHBOARD - ERICK',
    layout='wide'
)

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

# ====================================================================
# URL GLOBAL
# ====================================================================
url = 'https://labdados.com/produtos'

# ====================================================================
# FUNÇÃO DE FORMATAÇÃO
# ====================================================================
def formata_numero(valor, prefixo=''):
    if pd.isna(valor) or np.isinf(valor):
        return f'{prefixo} 0.00'
    for unidade in ['', 'mil']:
        if valor < 1000:
            return f'{prefixo} {valor:.2f} {unidade}'
        valor /= 1000
    return f'{prefixo} {valor:.2f} milhões'

# ====================================================================
# TELA DE CARREGAMENTO  mostra só na 1ª vez
# ====================================================================
placeholder = None
if 'dados_brutos' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            """
            <style>
                .splash-container {
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    font-size: 2em;
                    color: #555555;
                }
            </style>
            <div class="splash-container">
                <h1>CARREGANDO DASHBOARD VENDAS...</h1>
                <div class="loader"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ====================================================================
# CARREGAMENTO DE DADOS  usa cache e mantém na sessão
# ====================================================================
@st.cache_data(ttl=600, show_spinner=False)
def carregar_dados_brutos(api_url):
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        df = pd.DataFrame.from_dict(response.json())
        df['Data da Compra'] = pd.to_datetime(df['Data da Compra'], format='%d/%m/%Y')
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de Conexão {e}")
        return None

if 'dados_brutos' in st.session_state and isinstance(st.session_state['dados_brutos'], pd.DataFrame):
    dados_brutos = st.session_state['dados_brutos']
else:
    dados_brutos = carregar_dados_brutos(url)
    if dados_brutos is None:
        st.stop()
    st.session_state['dados_brutos'] = dados_brutos

if placeholder is not None:
    placeholder.empty()

# ====================================================================
# FILTROS
# ====================================================================
st.title('DASHBOARD DE VENDAS :shopping_cart:')
regioes = ['Brasil', 'Centro-Oeste', 'Nordeste', 'Sudeste', 'Sul']
anos_disponiveis = sorted(dados_brutos['Data da Compra'].dt.year.unique().tolist())
anos_disponiveis_str = [str(a) for a in anos_disponiveis]

st.sidebar.title('Filtros')

with st.sidebar.expander('Região'):
    data_regiao = st.selectbox('Selecione a região', regioes)
    regiao = '' if data_regiao == 'Brasil' else data_regiao

with st.sidebar.expander('Vendedores'):
    opcoes_vendedores = ['Todos'] + sorted(dados_brutos['Vendedor'].unique().tolist())
    vendedor_selecionado = st.multiselect('Selecione os vendedores', opcoes_vendedores, default=['Todos'])
    filtro_vendedores = [] if 'Todos' in vendedor_selecionado or not vendedor_selecionado else vendedor_selecionado

with st.sidebar.expander('Período'):
    filtro_anos = st.multiselect(
        'Selecione os anos',
        anos_disponiveis_str,
        default=anos_disponiveis_str
    )
    ano_param = ",".join(filtro_anos) if filtro_anos else ''

# ====================================================================
# REQUISIÇÃO FILTRADA
# ====================================================================
query_string = {'regiao': regiao.lower(), 'ano': ano_param}
response = requests.get(url, params=query_string)

if response.status_code == 200:
    dados = pd.DataFrame.from_dict(response.json())
    dados['Data da Compra'] = pd.to_datetime(dados['Data da Compra'], format='%d/%m/%Y')
else:
    st.error(f"Erro ao carregar dados. Código: {response.status_code}")
    dados = pd.DataFrame()

if filtro_vendedores:
    dados = dados[dados['Vendedor'].isin(filtro_vendedores)]

if dados.empty:
    st.warning('Nenhum dado encontrado com os filtros selecionados.')
    st.stop()

# ====================================================================
# AGRUPAMENTO E GRÁFICOS
# ====================================================================
@st.cache_data
def criar_tabelas_e_graficos(dados_filtrados):
    if dados_filtrados.empty:
        return (
            pd.DataFrame(), pd.DataFrame(),
            None, None, None, None,
            None, None, None, None,
        )

    receita_estados = dados_filtrados.groupby('Local da compra')['Preço'].sum()
    receita_estados = (
        dados_filtrados.drop_duplicates(subset='Local da compra')[['Local da compra', 'lat', 'lon']]
        .merge(receita_estados, left_on='Local da compra', right_index=True)
        .sort_values('Preço', ascending=False)
    )

    receita_mensal = (
        dados_filtrados.set_index('Data da Compra')
        .groupby(pd.Grouper(freq='ME'))['Preço'].sum()
        .reset_index()
    )
    receita_mensal['Ano'] = receita_mensal['Data da Compra'].dt.year
    receita_mensal['Mes'] = receita_mensal['Data da Compra'].dt.month_name()

    receita_categorias = (
        dados_filtrados.groupby('Categoria do Produto')[['Preço']].sum()
        .sort_values('Preço', ascending=False)
    )

    vendas_estados = dados_filtrados.groupby('Local da compra').size().reset_index(name='Contagem')
    vendas_estados = (
        dados_filtrados.drop_duplicates(subset='Local da compra')[['Local da compra', 'lat', 'lon']]
        .merge(vendas_estados, on='Local da compra')
        .sort_values('Contagem', ascending=False)
    )

    vendas_mensal = (
        dados_filtrados.set_index('Data da Compra')
        .groupby(pd.Grouper(freq='ME')).size()
        .reset_index(name='Contagem')
    )
    vendas_mensal['Ano'] = vendas_mensal['Data da Compra'].dt.year
    vendas_mensal['Mes'] = vendas_mensal['Data da Compra'].dt.month_name()

    vendas_categorias = (
        dados_filtrados.groupby('Categoria do Produto').size()
        .reset_index(name='Contagem')
        .sort_values('Contagem', ascending=False)
    )

    vendedores = pd.DataFrame(
        dados_filtrados.groupby('Vendedor')['Preço'].agg(['sum', 'count'])
    )

    RECEITA_MIN = receita_mensal['Preço'].min()
    RECEITA_MAX = receita_mensal['Preço'].max()
    VENDAS_MIN = vendas_mensal['Contagem'].min()
    VENDAS_MAX = vendas_mensal['Contagem'].max()

    fig_mapa_receita = px.scatter_geo(
        receita_estados,
        lat='lat', lon='lon', scope='south america', size='Preço', template='seaborn',
        hover_name='Local da compra', hover_data={'lat': False, 'lon': False},
        title='Receita por Estado',
    )
    fig_receita_mensal = px.line(
        receita_mensal, x='Mes', y='Preço', markers=True,
        range_y=(RECEITA_MIN * 0.9, RECEITA_MAX * 1.1), color='Ano', line_dash='Ano',
        title='Receita Mensal',
    )
    fig_receita_mensal.update_layout(yaxis_title='Receita')
    fig_receita_estados = px.bar(
        receita_estados.head(), x='Local da compra', y='Preço', text_auto=True,
        title='Top Estados Receita',
    )
    fig_receita_estados.update_layout(yaxis_title='Receita')
    fig_receitas_categorias = px.bar(
        receita_categorias, text_auto=True, title='Receita por Categorias',
    )
    fig_receitas_categorias.update_layout(yaxis_title='Receita')

    fig_mapa_vendas = px.scatter_geo(
        vendas_estados,
        lat='lat', lon='lon', scope='south america', size='Contagem', template='seaborn',
        hover_name='Local da compra', hover_data={'lat': False, 'lon': False},
        title='Quantidade de Vendas por Estado',
    )
    fig_vendas_mensal = px.line(
        vendas_mensal, x='Mes', y='Contagem', markers=True,
        range_y=((VENDAS_MIN - 20), VENDAS_MAX + 20), color='Ano', line_dash='Ano',
        title='Quantidade de Vendas Mensais',
    )
    fig_vendas_mensal.update_layout(yaxis_title='Quantidade de Vendas')
    fig_vendas_estados = px.bar(
        vendas_estados.head(), x='Local da compra', y='Contagem', text_auto=True,
        title='Top Estados Quantidade de Vendas',
    )
    fig_vendas_estados.update_layout(yaxis_title='Quantidade de Vendas')
    fig_vendas_categorias = px.bar(
        vendas_categorias, x='Contagem', y='Categoria do Produto', text_auto=True,
        title='Quantidade de Vendas por Categoria',
    )
    fig_vendas_categorias.update_layout(xaxis_title='Quantidade de Vendas', yaxis_title='Categoria')

    return (
        dados_filtrados, vendedores,
        fig_mapa_receita, fig_receita_mensal, fig_receita_estados, fig_receitas_categorias,
        fig_mapa_vendas, fig_vendas_mensal, fig_vendas_estados, fig_vendas_categorias,
    )

# Executa os cálculos com cache
dados_final, vendedores, fig_mapa_receita, fig_receita_mensal, fig_receita_estados, fig_receitas_categorias, fig_mapa_vendas, fig_vendas_mensal, fig_vendas_estados, fig_vendas_categorias = criar_tabelas_e_graficos(dados)

# ====================================================================
# MÉTRICAS DINÂMICAS GERAIS
# ====================================================================
qtd_operadores = int(dados_final['Vendedor'].nunique()) if 'Vendedor' in dados_final.columns else 0
media_avaliacao = float(dados_final['Avaliação da compra'].mean()) if 'Avaliação da compra' in dados_final.columns else float('nan')

# ====================================================================
# VISUALIZAÇÃO
# ====================================================================
if not dados_final.empty:
    aba1, aba2, aba3, aba4 = st.tabs(['Receita', 'Quantidade de Vendas', 'Vendedores', 'Data Frame'])

    # ---------------------------------------------------------------
    # ABA 1 - RECEITA
    # ---------------------------------------------------------------
    with aba1:
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric('Receita Total', formata_numero(dados_final['Preço'].sum(), 'R$'))
        with m2:
            st.metric('Quantidade de Vendas', formata_numero(dados_final.shape[0]))
        with m3:
            st.metric('Quantidade de Operadores', f'{qtd_operadores}')
        with m4:
            st.metric('Média Avaliação da compra', f"{media_avaliacao:.2f}" if not np.isnan(media_avaliacao) else 'Sem dados')

        c1, c2 = st.columns(2)
        with c1:
            show_chart(fig_mapa_receita)
            show_chart(fig_receita_estados)
        with c2:
            show_chart(fig_receita_mensal)
            show_chart(fig_receitas_categorias)

    # ---------------------------------------------------------------
    # ABA 2 - QUANTIDADE DE VENDAS
    # ---------------------------------------------------------------
    with aba2:
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric('Receita Total', formata_numero(dados_final['Preço'].sum(), 'R$'))
        with m2:
            st.metric('Quantidade de Vendas', formata_numero(dados_final.shape[0]))
        with m3:
            st.metric('Quantidade de Operadores', f'{qtd_operadores}')
        with m4:
            st.metric('Média Avaliação da compra', f"{media_avaliacao:.2f}" if not np.isnan(media_avaliacao) else 'Sem dados')

        c1, c2 = st.columns(2)
        with c1:
            show_chart(fig_mapa_vendas)
            show_chart(fig_vendas_estados)
        with c2:
            show_chart(fig_vendas_mensal)
            show_chart(fig_vendas_categorias)

    # ---------------------------------------------------------------
    # ABA 3 - VENDEDORES
    # ---------------------------------------------------------------
    with aba3:
        qtd_vendedores = st.number_input('Quantidade de vendedores', 2, 10, 5)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric('Receita Total', formata_numero(dados_final['Preço'].sum(), 'R$'))
        with m2:
            st.metric('Quantidade de Vendas', formata_numero(dados_final.shape[0]))
        with m3:
            st.metric('Quantidade de Operadores', f'{qtd_operadores}')
        with m4:
            st.metric('Média Avaliação da compra', f"{media_avaliacao:.2f}" if not np.isnan(media_avaliacao) else 'Sem dados')

        c1, c2 = st.columns(2)

        # Receita por vendedor
        with c1:
            fig_receita_vendedores = px.bar(
                vendedores[['sum']].sort_values('sum', ascending=False).head(qtd_vendedores),
                x='sum',
                y=vendedores[['sum']].sort_values('sum', ascending=False).head(qtd_vendedores).index,
                text_auto=True,
                title=f'Top{qtd_vendedores} vendedores receita',
            )
            show_chart(fig_receita_vendedores)

        # Quantidade com média escrita ao final da mesma barra
        with c2:
            df_top = (
                dados_final.groupby('Vendedor').agg(
                    Quantidade=('Preço', 'count'),
                    MediaAvaliacao=('Avaliação da compra', 'mean'),
                )
                .reset_index()
                .sort_values('Quantidade', ascending=False)
                .head(qtd_vendedores)
            )

            media_vals = df_top['MediaAvaliacao'].round(2)
            text_vals = media_vals.where(~media_vals.isna(), other='Sem dados').astype(str)

            fig_vendas_vendedores = px.bar(
                df_top,
                x='Quantidade',
                y='Vendedor',
                orientation='h',
                title=f'Top{qtd_vendedores} vendedores quantidade com média ao final da barra',
                hover_data={'MediaAvaliacao': ':.2f'},
            )
            fig_vendas_vendedores.update_traces(
                text=text_vals,
                texttemplate='Média: %{text}',
                textposition='outside',
            )
            fig_vendas_vendedores.update_layout(
                xaxis_title='Quantidade de vendas',
                yaxis_title='Vendedor',
            )
            show_chart(fig_vendas_vendedores)

    # ---------------------------------------------------------------
    # ABA 4 - DATA FRAME
    # ---------------------------------------------------------------
    with aba4:
        st.dataframe(dados_brutos, width='stretch')
