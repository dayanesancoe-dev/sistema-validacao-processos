import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime
import sqlite3
import pandas as pd

st.set_page_config(page_title="Sistema de Validação - Prefeitura Contagem", page_icon="🏛️", layout="wide")

# ==================== BANCO DE DADOS ====================

@st.cache_resource
def init_db():
    """Inicializa o banco de dados"""
    conn = sqlite3.connect('processos.db', check_same_thread=False)
    cursor = conn.cursor()

    # Criar tabela de processos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_processo TEXT UNIQUE NOT NULL,
            responsavel_tecnico TEXT NOT NULL,
            requerente TEXT NOT NULL,
            analista TEXT NOT NULL,
            uso TEXT NOT NULL,
            tipologia TEXT NOT NULL,
            area_construida REAL NOT NULL,
            data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Criar tabela de PDFs do projeto
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdfs_projeto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            nome_arquivo TEXT NOT NULL,
            conteudo BLOB NOT NULL,
            tipo TEXT,
            data_upload TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )
    ''')

    # Criar tabela de PDFs da legislação
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdfs_legislacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            nome_arquivo TEXT NOT NULL,
            conteudo BLOB NOT NULL,
            data_upload TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )
    ''')

    # Criar tabela de análises
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            status TEXT NOT NULL,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )
    ''')

    conn.commit()
    return conn, cursor

conn, cursor = init_db()

# ==================== FUNÇÕES DO BANCO ====================

def cadastrar_processo(numero, rt, requerente, analista, uso, tipologia, area):
    """Cadastra novo processo"""
    try:
        cursor.execute('''
            INSERT INTO processos (numero_processo, responsavel_tecnico, requerente, analista, uso, tipologia, area_construida)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (numero, rt, requerente, analista, uso, tipologia, area))
        conn.commit()
        return True, "✅ Processo cadastrado com sucesso!"
    except sqlite3.IntegrityError:
        return False, f"❌ Processo {numero} já existe!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def listar_processos():
    """Lista todos os processos"""
    cursor.execute('SELECT * FROM processos ORDER BY data_cadastro DESC')
    return cursor.fetchall()

def buscar_processo(numero):
    """Busca processo pelo número"""
    cursor.execute('SELECT * FROM processos WHERE numero_processo = ?', (numero,))
    return cursor.fetchone()

def buscar_processo_por_id(processo_id):
    """Busca processo pelo ID"""
    cursor.execute('SELECT * FROM processos WHERE id = ?', (processo_id,))
    return cursor.fetchone()

def atualizar_processo(processo_id, numero, rt, requerente, analista, uso, tipologia, area):
    """Atualiza dados do processo"""
    try:
        cursor.execute('''
            UPDATE processos 
            SET numero_processo=?, responsavel_tecnico=?, requerente=?, analista=?, uso=?, tipologia=?, area_construida=?
            WHERE id=?
        ''', (numero, rt, requerente, analista, uso, tipologia, area, processo_id))
        conn.commit()
        return True, "✅ Processo atualizado!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def deletar_processo(processo_id):
    """Deleta processo"""
    try:
        cursor.execute('DELETE FROM pdfs_projeto WHERE processo_id = ?', (processo_id,))
        cursor.execute('DELETE FROM pdfs_legislacao WHERE processo_id = ?', (processo_id,))
        cursor.execute('DELETE FROM analises WHERE processo_id = ?', (processo_id,))
        cursor.execute('DELETE FROM processos WHERE id = ?', (processo_id,))
        conn.commit()
        return True, "✅ Processo deletado!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def salvar_analise(processo_id, resultado, status):
    """Salva resultado da análise"""
    try:
        cursor.execute('INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)',
                      (processo_id, resultado, status))
        conn.commit()
        return True
    except:
        return False

def buscar_analises(processo_id):
    """Busca análises de um processo"""
    cursor.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY data_analise DESC', (processo_id,))
    return cursor.fetchall()

# ==================== INTERFACE ====================

st.title("🏛️ Sistema de Validação de Processos")
st.markdown("**Prefeitura de Contagem** — Setor de Liberação de Alvarás")

# Sidebar - Configuração API
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("API Key do Google Gemini:", type="password", help="Obtenha em: https://aistudio.google.com/app/apikey")

    if api_key:
        st.success("✅ API configurada!")
        try:
            genai.configure(api_key=api_key)
        except:
            st.error("❌ Erro na API Key")
    else:
        st.warning("⚠️ Configure a API Key")
        st.markdown("[🔗 Obter API Key](https://aistudio.google.com/app/apikey)")

    st.divider()
    st.metric("Total de Processos", len(listar_processos()))

# Abas principais
tab1, tab2, tab3 = st.tabs(["📝 Cadastrar Processo", "📋 Gerenciar Processos", "🤖 Análise com IA"])

# ==================== ABA 1: CADASTRAR PROCESSO ====================
with tab1:
    st.header("📝 Cadastrar Novo Processo")

    with st.form("form_cadastro", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            numero = st.text_input("Número do Processo *", placeholder="Ex: 2024.001.123")
            rt = st.text_input("Responsável Técnico *", placeholder="Nome do RT")
            requerente = st.text_input("Requerente *", placeholder="Nome do requerente")
            analista = st.text_input("Analista *", placeholder="Nome do analista")

        with col2:
            uso = st.selectbox("Uso *", ["", "Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"])
            tipologia = st.selectbox("Tipologia *", ["", "Casa", "Sobrado", "Edifício", "Galpão", "Loja", "Sala Comercial", "Outro"])
            area = st.number_input("Área Construída (m²) *", min_value=0.0, step=0.01, format="%.2f")

        st.markdown("*Campos obrigatórios")

        submitted = st.form_submit_button("✅ Cadastrar Processo", use_container_width=True, type="primary")

        if submitted:
            if not numero or not rt or not requerente or not analista or not uso or not tipologia or area <= 0:
                st.error("❌ Preencha todos os campos obrigatórios!")
            else:
                sucesso, mensagem = cadastrar_processo(numero, rt, requerente, analista, uso, tipologia, area)
                if sucesso:
                    st.success(mensagem)
                    st.balloons()
                else:
                    st.error(mensagem)

# ==================== ABA 2: GERENCIAR PROCESSOS ====================
with tab2:
    st.header("📋 Gerenciar Processos")

    processos = listar_processos()

    if not processos:
        st.info("📭 Nenhum processo cadastrado ainda. Cadastre na aba anterior.")
    else:
        # Filtros
        col_filtro1, col_filtro2, col_filtro3 = st.columns(3)

        with col_filtro1:
            filtro_numero = st.text_input("🔍 Buscar por número:", key="filtro_num")
        with col_filtro2:
            filtro_analista = st.text_input("🔍 Buscar por analista:", key="filtro_ana")
        with col_filtro3:
            filtro_uso = st.selectbox("🔍 Filtrar por uso:", ["Todos", "Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"], key="filtro_uso")

        # Aplicar filtros
        processos_filtrados = processos
        if filtro_numero:
            processos_filtrados = [p for p in processos_filtrados if filtro_numero.lower() in p[1].lower()]
        if filtro_analista:
            processos_filtrados = [p for p in processos_filtrados if filtro_analista.lower() in p[4].lower()]
        if filtro_uso != "Todos":
            processos_filtrados = [p for p in processos_filtrados if p[5] == filtro_uso]

        st.divider()
        st.write(f"**Exibindo {len(processos_filtrados)} de {len(processos)} processos**")

        # Mostrar processos
        for processo in processos_filtrados:
            processo_id, numero, rt, requerente, analista, uso, tipologia, area, data = processo

            with st.expander(f"📄 {numero} - {requerente}", expanded=False):
                col_info, col_acoes = st.columns([3, 1])

                with col_info:
                    st.write(f"**RT:** {rt}")
                    st.write(f"**Requerente:** {requerente}")
                    st.write(f"**Analista:** {analista}")
                    st.write(f"**Uso:** {uso} | **Tipologia:** {tipologia}")
                    st.write(f"**Área:** {area}m²")
                    st.write(f"**Cadastrado em:** {data}")

                    # Mostrar análises
                    analises = buscar_analises(processo_id)
                    if analises:
                        st.divider()
                        st.write("**📊 Análises realizadas:**")
                        for analise in analises:
                            status_icon = "✅" if analise[3] == "APROVADO" else "❌"
                            st.write(f"{status_icon} {analise[4]} - {analise[3]}")

                with col_acoes:
                    if st.button("✏️ Editar", key=f"edit_{processo_id}"):
                        st.session_state[f'editando_{processo_id}'] = True
                        st.rerun()

                    if st.button("🗑️ Deletar", key=f"del_{processo_id}"):
                        sucesso, msg = deletar_processo(processo_id)
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                # Formulário de edição
                if st.session_state.get(f'editando_{processo_id}', False):
                    st.divider()
                    st.subheader("✏️ Editar Processo")

                    with st.form(f"form_edit_{processo_id}"):
                        col1, col2 = st.columns(2)

                        with col1:
                            novo_numero = st.text_input("Número", value=numero, key=f"num_{processo_id}")
                            novo_rt = st.text_input("RT", value=rt, key=f"rt_{processo_id}")
                            novo_req = st.text_input("Requerente", value=requerente, key=f"req_{processo_id}")
                            novo_ana = st.text_input("Analista", value=analista, key=f"ana_{processo_id}")

                        with col2:
                            novo_uso = st.selectbox("Uso", ["Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"], 
                                                   index=["Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"].index(uso),
                                                   key=f"uso_{processo_id}")
                            nova_tip = st.selectbox("Tipologia", ["Casa", "Sobrado", "Edifício", "Galpão", "Loja", "Sala Comercial", "Outro"],
                                                   index=["Casa", "Sobrado", "Edifício", "Galpão", "Loja", "Sala Comercial", "Outro"].index(tipologia),
                                                   key=f"tip_{processo_id}")
                            nova_area = st.number_input("Área (m²)", value=float(area), step=0.01, key=f"area_{processo_id}")

                        col_btn1, col_btn2 = st.columns(2)

                        with col_btn1:
                            if st.form_submit_button("💾 Salvar", use_container_width=True, type="primary"):
                                sucesso, msg = atualizar_processo(processo_id, novo_numero, novo_rt, novo_req, novo_ana, novo_uso, nova_tip, nova_area)
                                if sucesso:
                                    st.success(msg)
                                    del st.session_state[f'editando_{processo_id}']
                                    st.rerun()
                                else:
                                    st.error(msg)

                        with col_btn2:
                            if st.form_submit_button("❌ Cancelar", use_container_width=True):
                                del st.session_state[f'editando_{processo_id}']
                                st.rerun()

# ==================== ABA 3: ANÁLISE COM IA ====================
with tab3:
    st.header("🤖 Análise com Inteligência Artificial")

    if not api_key:
        st.warning("⚠️ Configure sua API Key na barra lateral para usar esta função")
        st.stop()

    processos = listar_processos()

    if not processos:
        st.info("📭 Cadastre um processo primeiro na aba 'Cadastrar Processo'")
        st.stop()

    # Selecionar processo
    opcoes_processos = [f"{p[1]} - {p[3]}" for p in processos]
    processo_selecionado = st.selectbox("Selecione o Processo:", opcoes_processos, key="sel_proc_analise")

    if processo_selecionado:
        numero_proc = processo_selecionado.split(" - ")[0]
        processo_dados = buscar_processo(numero_proc)

        if processo_dados:
            # Mostrar dados do processo
            with st.expander("📋 Dados do Processo", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Número", processo_dados[1])
                col2.metric("Uso", processo_dados[5])
                col3.metric("Área", f"{processo_dados[7]}m²")

                st.write(f"**RT:** {processo_dados[2]}")
                st.write(f"**Requerente:** {processo_dados[3]}")
                st.write(f"**Analista:** {processo_dados[4]}")
                st.write(f"**Tipologia:** {processo_dados[6]}")

            st.divider()

            # Upload de arquivos
            col_up1, col_up2 = st.columns(2)

            with col_up1:
                st.subheader("📐 PDFs do Projeto")
                projetos = st.file_uploader("Anexe os PDFs", type=['pdf'], accept_multiple_files=True, key="pdfs_proj_analise")
                if projetos:
                    st.success(f"✅ {len(projetos)} arquivo(s)")

            with col_up2:
                st.subheader("📜 PDFs da Legislação")
                legislacoes = st.file_uploader("Anexe os PDFs", type=['pdf'], accept_multiple_files=True, key="pdfs_leg_analise")
                if legislacoes:
                    st.success(f"✅ {len(legislacoes)} arquivo(s)")

            st.divider()
            st.subheader("📏 Regras a Verificar")
            regras = st.text_area("Digite as regras (uma por linha):", height=150, 
                                 placeholder="Ex:\nArt. 10 - Área mínima 50m²\nArt. 15 - Recuo frontal 5m",
                                 key="regras_analise")

            st.divider()

            # Botão de análise
            if st.button("🔍 ANALISAR PROJETO", type="primary", use_container_width=True):
                if not projetos or not legislacoes or not regras:
                    st.error("❌ Anexe os PDFs e digite as regras!")
                else:
                    with st.spinner("🤖 Analisando com IA..."):
                        try:
                            # Extrair textos
                            texto_proj = ""
                            for pdf in projetos:
                                reader = PyPDF2.PdfReader(pdf)
                                for page in reader.pages:
                                    texto_proj += page.extract_text() + "\n"

                            texto_leg = ""
                            for pdf in legislacoes:
                                reader = PyPDF2.PdfReader(pdf)
                                for page in reader.pages:
                                    texto_leg += page.extract_text() + "\n"

                            # Criar modelo
                            modelos = ['models/gemini-pro', 'gemini-pro', 'models/gemini-1.5-pro-latest']
                            model = None

                            for nome_modelo in modelos:
                                try:
                                    model = genai.GenerativeModel(nome_modelo)
                                    break
                                except:
                                    continue

                            if not model:
                                st.error("❌ Nenhum modelo disponível")
                                st.stop()

                            # Prompt
                            prompt = f"""Analista da Prefeitura de Contagem.

PROCESSO: {processo_dados[1]}
REQUERENTE: {processo_dados[3]}
RT: {processo_dados[2]}
USO: {processo_dados[5]}
TIPOLOGIA: {processo_dados[6]}
ÁREA: {processo_dados[7]}m²

LEGISLAÇÃO:
{texto_leg[:4000]}

REGRAS:
{regras}

PROJETO:
{texto_proj[:6000]}

Analise:

## ✅ CONFORMIDADES
( artigos)

## ❌ NÃO CONFORMIDADES
(cite artigos e localize)

## ⚠️ PONTOS DE ATENÇÃO

## 🔧 RECOMENDAÇÕES

## 📊 PARECER
APROVADO ou REPROVADO (justifique)
"""

                            response = model.generate_content(prompt)

                            # Determinar status
                            texto_resp = response.text.upper()
                            if "APROVADO" in texto_resp and "REPROVADO" not in texto_resp:
                                status = "APROVADO"
                                st.success("✅ PROJETO APROVADO")
                            elif "REPROVADO" in texto_resp:
                                status = "REPROVADO"
                                st.error("❌ PROJETO REPROVADO")
                            else:
                                status = "INCONCLUSIVO"
                                st.warning("⚠️ ANÁLISE INCONCLUSIVA")

                            st.divider()
                            st.markdown(response.text)

                            # Salvar análise
                            salvar_analise(processo_dados[0], response.text, status)

                            # Download
                            relatorio = f"""PREFEITURA DE CONTAGEM
RELATÓRIO DE ANÁLISE

Processo: {processo_dados[1]}
Requerente: {processo_dados[3]}
RT: {processo_dados[2]}
Analista: {processo_dados[4]}
Uso: {processo_dados[5]}
Tipologia: {processo_dados[6]}
Área: {processo_dados[7]}m²
Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}

{response.text}
"""

                            st.download_button(
                                "📥 BAIXAR RELATÓRIO",
                                relatorio,
                                f"relatorio_{processo_dados[1].replace('.', '_')}.txt",
                                type="primary",
                                use_container_width=True
                            )

                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")

st.divider()
st.markdown("---")
st.markdown("🏛️ **Sistema de Validação** • Prefeitura de Contagem • Powered by Google Gemini")
