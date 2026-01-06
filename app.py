import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os
# Removido bcrypt pois a gestão de usuários foi simplificada

# ==================== Importação de bibliotecas opcionais (para gráficos) ====================
try:
    import pandas as pd
    import plotly.express as px
except ImportError:
    pd = None
    px = None
    st.error("❌ Erro: As bibliotecas 'pandas' e 'plotly' não foram encontradas. A aba de gráficos não funcionará. Por favor, verifique seu 'requirements.txt' e faça um 'Clear cache and redeploy' no Streamlit Share.")

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== INICIALIZAÇÃO DE ESTADO ====================
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''
if 'db_reset_needed_rerun' not in st.session_state:
    st.session_state['db_reset_needed_rerun'] = False
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state: # Adicionado para armazenar o nome de usuário logado
    st.session_state['username'] = None

if st.session_state['db_reset_needed_rerun']:
    st.session_state['db_reset_needed_rerun'] = False
    st.rerun()

# ==================== BANCO DE DADOS ====================

# A função reset_database foi removida para simplificar e evitar o erro persistente.
# Se precisar resetar o banco, você terá que deletar o arquivo 'processos.db' manualmente no ambiente do Streamlit Share
# (se tiver acesso aos arquivos) ou recriar o app.

@st.cache_resource
def init_db():
    """Inicializa o banco de dados, criando tabelas se não existirem ou se o schema estiver desatualizado."""
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()

        expected_processos_column_names = [
            'id', 'numero', 'rt', 'requerente', 'analista', 'uso', 
            'tipologia', 'area', 'data_protocolo', 'status', 'data_cadastro'
        ]

        schema_outdated = False

        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processos'")
        table_exists = c.fetchone()

        if table_exists:
            c.execute("PRAGMA table_info(processos)")
            current_columns_info = c.fetchall()
            current_column_names = [col[1] for col in current_columns_info]

            if not (set(expected_processos_column_names) == set(current_column_names) and 
                    len(expected_processos_column_names) == len(current_column_names)):
                schema_outdated = True
        else:
            schema_outdated = True

        if schema_outdated:
            st.warning("⚠️ Detectada estrutura de banco de dados antiga ou inconsistente. Recriando tabelas...")
            c.execute('DROP TABLE IF EXISTS tramitacao')
            c.execute('DROP TABLE IF EXISTS analises')
            c.execute('DROP TABLE IF EXISTS processos')
            # Removido 'DROP TABLE IF EXISTS users' pois a tabela de usuários não será mais usada
            conn.commit()

            c.execute('''CREATE TABLE processos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE NOT NULL,
                rt TEXT NOT NULL,
                requerente TEXT NOT NULL,
                analista TEXT NOT NULL,
                uso TEXT NOT NULL,
                tipologia TEXT NOT NULL,
                area REAL NOT NULL,
                data_protocolo TEXT NOT NULL,
                status TEXT DEFAULT 'Protocolado',
                data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.commit()

        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            status TEXT NOT NULL,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS tramitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            setor TEXT NOT NULL,
            data_entrada TEXT NOT NULL,
            data_saida TEXT,
            observacao TEXT,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        # Removida a criação da tabela 'users'

        conn.commit()
        return conn
    except Exception as e:
        st.error(f"❌ Erro ao inicializar o banco de dados: {str(e)}")
        return None

conn = init_db()

# ==================== FUNÇÕES CRUD (PROCESSOS) ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area, data_protocolo):
    """Cadastra um novo processo no banco de dados.""..m que o projeto parece estar em conformidade com normas gerais de construção e urbanismo (ex: recuos, taxa de ocupação, coeficiente de aproveitamento, ventilação, iluminação, acessibilidade, etc.).
3.  **Não Conformidade/Pendências:** Pontos que precisam de correção ou esclarecimento para a aprovação. Seja específico sobre quais itens estão em desacordo ou quais informações estão faltando.
4.  **Recomendação Final:**
    *   Se o projeto parece estar em total conformidade e pronto para aprovação, termine o parecer com a frase **"RECOMENDAÇÃO: PROJETO APROVADO"**.
    *   Se o projeto possui pendências ou não conformidades que exigem correção, termine o parecer com a frase **"RECOMENDAÇÃO: PROJETO REPROVADO"**.
    *   Se a análise for inconclusiva devido à falta de informações críticas no PDF ou se o PDF for apenas parcial, termine o parecer com a frase **"RECOMENDAÇÃO: ANÁLISE INCONCLUSIVA"**.

---
**TEXTO DO PROJETO ARQUITETÔNICO:**
{txt_proj[:15000]} # Limita o texto para evitar estouro de token
---
"""

                                    resposta = model.generate_content(prompt)

                                    texto_resposta = resposta.text

                                    status_analise = "INCONCLUSIVO"
                                    if "APROVADO" in texto_resposta.upper() and "REPROVADO" not in texto_resposta.upper():
                                        status_analise = "APROVADO"
                                        st.success("✅ PROJETO APROVADO")
                                        atualizar_status(dados[0], "Aprovado")
                                    elif "REPROVADO" in texto_resposta.upper():
                                        status_analise = "REPROVADO"
                                        st.error("❌ PROJETO REPROVADO")
                                        atualizar_status(dados[0], "Reprovado")
                                    else:
                                        st.warning("⚠️ ANÁLISE INCONCLUSIVA")
                                        atualizar_status(dados[0], "Em Análise")

                                    st.divider()

                                    st.markdown(resposta.text)

                                    salvar_analise(dados[0], resposta.text, status_analise)

                                    relatorio = f"""PREFEITURA DE CONTAGEM - MG
RELATÓRIO DE ANÁLISE TÉCNICA DE PROJETO ARQUITETÔNICO

Processo: {dados[1]}
Responsável Técnico: {dados[2]}
Requerente: {dados[3]}
Analista: {dados[4]}
Uso: {dados[5]}
Tipologia: {dados[6]}
Área Construída: {dados[7]}m²
Data do Protocolo: {datetime.strptime(dados[8], '%Y-%m-%d').strftime('%d/%m/%Y')}
Status do Processo: {dados[9]}
Data da Análise: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

{'='*80}

{resposta.text}

{'='*80}
Relatório gerado automaticamente por Inteligência Artificial (Google Gemini)
Sistema de Validação de Processos - Prefeitura de Contagem
"""

                                    st.divider()

                                    st.download_button(
                                        label="📥 BAIXAR RELATÓRIO COMPLETO (TXT)",
                                        data=relatorio,
                                        file_name=f"relatorio_processo_{dados[1].replace('.', '_').replace('/', '_')}.txt",
                                        mime="text/plain",
                                        type="primary",
                                        use_container_width=True
                                    )

                                except Exception as erro:
                                    st.error(f"❌ Erro durante a análise: {str(erro)}")
                                    st.info("Verifique se sua API Key está correta e a disponibilidade dos modelos do Gemini.")

    with tab6:
        st.header("📈 Análise Gráfica dos Processos")

        if pd is None or px is None:
            st.error("❌ As bibliotecas de gráficos (pandas, plotly) não estão disponíveis. Verifique seu 'requirements.txt'.")
        else:
            procs_df = get_processos_df()

            if procs_df.empty:
                st.info("📭 Nenhum dado para gerar gráficos. Cadastre processos primeiro na aba 'Cadastrar'.")
            else:
                st.subheader("Selecione o tipo de gráfico para visualizar os dados:")
                chart_type = st.selectbox("Escolha a análise:", [
                    "Processos por Uso",
                    "Processos por Tipologia",
                    "Processos por Analista",
                    "Distribuição de Status Kanban",
                    "Área Total por Uso",
                    "Processos por Data de Protocolo"
                ])

                st.divider()

                if chart_type == "Processos por Uso":
                    st.markdown("### 📊 Quantidade de Processos por Tipo de Uso")
                    df_grouped = procs_df['uso'].value_counts().reset_index()
                    df_grouped.columns = ['Uso', 'Quantidade']
                    fig = px.bar(df_grouped, x='Uso', y='Quantidade', 
                                 title='Número de Processos por Tipo de Uso',
                                 labels={'Uso': 'Tipo de Uso', 'Quantidade': 'Número de Processos'},
                                 color='Uso', 
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Processos por Tipologia":
                    st.markdown("### 📊 Quantidade de Processos por Tipologia")
                    df_grouped = procs_df['tipologia'].value_counts().reset_index()
                    df_grouped.columns = ['Tipologia', 'Quantidade']
                    fig = px.bar(df_grouped, x='Tipologia', y='Quantidade', 
                                 title='Número de Processos por Tipologia',
                                 labels={'Tipologia': 'Tipologia do Projeto', 'Quantidade': 'Número de Processos'},
                                 color='Tipologia',
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Processos por Analista":
                    st.markdown("### 📊 Quantidade de Processos por Analista")
                    df_grouped = procs_df['analista'].value_counts().reset_index()
                    df_grouped.columns = ['Analista', 'Quantidade']
                    fig = px.bar(df_grouped, x='Analista', y='Quantidade', 
                                 title='Número de Processos por Analista',
                                 labels={'Analista': 'Nome do Analista', 'Quantidade': 'Número de Processos'},
                                 color='Analista',
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Distribuição de Status Kanban":
                    st.markdown("### 📊 Distribuição de Processos por Status Kanban")
                    df_grouped = procs_df['status'].value_counts().reset_index()
                    df_grouped.columns = ['Status', 'Quantidade']
                    fig = px.pie(df_grouped, values='Quantidade', names='Status', 
                                 title='Distribuição Percentual de Processos por Status',
                                 hole=0.3, 
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Área Total por Uso":
                    st.markdown("### 📊 Área Construída Total por Tipo de Uso")
                    df_grouped = procs_df.groupby('uso')['area'].sum().reset_index()
                    df_grouped.columns = ['Uso', 'Area Total (m²)']
                    fig = px.bar(df_grouped, x='Uso', y='Area Total (m²)', 
                                 title='Área Construída Total por Tipo de Uso',
                                 labels={'Uso': 'Tipo de Uso', 'Area Total (m²)': 'Área Total (m²)'},
                                 color='Uso',
                                 template='plotly_white')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_type == "Processos por Data de Protocolo":
                    st.markdown("### 📊 Número de Processos Protocolados ao Longo do Tempo")
                    df_valid_dates = procs_df.dropna(subset=['data_protocolo'])
                    if not df_valid_dates.empty:
                        df_grouped = df_valid_dates.groupby(df_valid_dates['data_protocolo'].dt.to_period('M')).size().reset_index(name='Quantidade')
                        df_grouped['data_protocolo'] = df_grouped['data_protocolo'].dt.to_timestamp()

                        fig = px.line(df_grouped, x='data_protocolo', y='Quantidade', 
                                      title='Processos Protocolados por Mês',
                                      labels={'data_protocolo': 'Mês de Protocolo', 'Quantidade': 'Número de Processos'},
                                      template='plotly_white')
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Nenhum processo com data de protocolo válida para este gráfico.")


# ==================== LÓGICA PRINCIPAL DO APP ====================
if not st.session_state['logged_in']:
    login_form()
else:
    main_app_content()

# Rodapé
st.divider()
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p><strong>🏛️ Sistema de Validação de Processos com Inteligência Artificial</strong></p>
    <p>Prefeitura de Contagem - MG • Setor de Liberação de Alvarás de Construção</p>
    <p style='font-size: 0.85em; color: #666;'>Powered by Google Gemini, Streamlit, Plotly & Pandas</p>
</div>
""", unsafe_allow_html=True)
