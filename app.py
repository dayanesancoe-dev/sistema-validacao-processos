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
    conn = sqlite3.connect('processos.db', check_same_thread=False)
    cursor = conn.cursor()

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
    cursor.execute('SELECT * FROM processos ORDER BY data_cadastro DESC')
    return cursor.fetchall()

def buscar_processo(numero):
    cursor.execute('SELECT * FROM processos WHERE numero_processo = ?', (numero,))
    return cursor.fetchone()

def buscar_processo_por_id(processo_id):
    cursor.execute('SELECT * FROM processos WHERE id = ?', (processo_id,))
    return cursor.fetchone()

def atualizar_processo(processo_id, numero, rt, requerente, analista, uso, tipologia, area):
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
    try:
        cursor.execute('DELETE FROM analises WHERE processo_id = ?', (processo_id,))
        cursor.execute('DELETE FROM processos WHERE id = ?', (processo_id,))
        conn.commit()
        return True, "✅ Processo deletado!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def salvar_analise(processo_id, resultado, status):
    try:
        cursor.execute('INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)',
                      (processo_id, resultado, status))
        conn.commit()
        return True
    except:
        return False

def buscar_analises(processo_id):
    cursor.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY data_analise DESC', (processo_id,))
    return cursor.fetchall()

# ==================== INTERFACE ====================

st.title("🏛️ Sistema de Validação de Processos")
st.markdown("**Prefeitura de Contagem** — Setor de Liberação de Alvarás")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("API Key do Google Gemini:", type="password")

    if api_key:
        st.success("✅ API configurada!")
    else:
        st.warning("⚠️ Configure a API Key")
        st.markdown("[🔗 Obter API Key](https://aistudio.google.com/app/apikey)")

    st.divider()
    st.metric("Total de Processos", len(listar_processos()))

# Abas
tab1, tab2, tab3 = st.tabs(["📝 Cadastrar Processo", "📋 Gerenciar Processos", "🤖 Análise com IA"])

# ==================== ABA 1: CADASTRAR ====================
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

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Gerenciar Processos")

    processos = listar_processos()

    if not processos:
        st.info("📭 Nenhum processo cadastrado")
    else:
        # Filtros
        col1, col2, col3 = st.columns(3)
        with col1:
            filtro_num = st.text_input("🔍 Número:", key="filtro_n")
        with col2:
            filtro_ana = st.text_input("🔍 Analista:", key="filtro_a")
        with col3:
            filtro_uso = st.selectbox("🔍 Uso:", ["Todos", "Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"], key="filtro_u")

        # Aplicar filtros
        processos_filtrados = processos
        if filtro_num:
            processos_filtrados = [p for p in processos_filtrados if filtro_num.lower() in p[1].lower()]
        if filtro_ana:
            processos_filtrados = [p for p in processos_filtrados if filtro_ana.lower() in p[4].lower()]
        if filtro_uso != "Todos":
            processos_filtrados = [p for p in processos_filtrados if p[5] == filtro_uso]

        st.write(f"**{len(processos_filtrados)} de {len(processos)} processos**")

        for processo in processos_filtrados:
            # CORREÇÃO: desempacotar corretamente (8 colunas)
            pid, num, rt, req, ana, uso, tip, area, data = processo

            with st.expander(f"📄 {num} - {req}"):
                col_info, col_acoes = st.columns([3, 1])

                with col_info:
                    st.write(f"**RT:** {rt}")
                    st.write(f"**Requerente:** {req}")
                    st.write(f"**Analista:** {ana}")
                    st.write(f"**Uso:** {uso} | **Tipologia:** {tip}")
                    st.write(f"**Área:** {area}m²")
                    st.write(f"**Cadastrado:** {data}")

                    analises = buscar_analises(pid)
                    if analises:
                        st.divider()
                        st.write("**📊 Análises:**")
                        for analise in analises:
                            status_icon = "✅" if analise[3] == "APROVADO" else "❌"
                            st.write(f"{status_icon} {analise[4]} - {analise[3]}")

                with col_acoes:
                    if st.button("✏️", key=f"edit_{pid}"):
                        st.session_state[f'editando_{pid}'] = True
                        st.rerun()

                    if st.button("🗑️", key=f"del_{pid}"):
                        sucesso, msg = deletar_processo(pid)
                        if sucesso:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                # Edição
                if st.session_state.get(f'editando_{pid}', False):
                    st.divider()

                    with st.form(f"form_edit_{pid}"):
                        col1, col2 = st.columns(2)

                        with col1:
                            novo_num = st.text_input("Número", value=num, key=f"n_{pid}")
                            novo_rt = st.text_input("RT", value=rt, key=f"rt_{pid}")
                            novo_req = st.text_input("Requerente", value=req, key=f"req_{pid}")
                            novo_ana = st.text_input("Analista", value=ana, key=f"ana_{pid}")

                        with col2:
                            novo_uso = st.selectbox("Uso", ["Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"], 
                                                   index=["Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"].index(uso),
                                                   key=f"uso_{pid}")
                            nova_tip = st.selectbox("Tipologia", ["Casa", "Sobrado", "Edifício", "Galpão", "Loja", "Sala Comercial", "Outro"],
                                                   index=["Casa", "Sobrado", "Edifício", "Galpão", "Loja", "Sala Comercial", "Outro"].index(tip),
                                                   key=f"tip_{pid}")
                            nova_area = st.number_input("Área", value=float(area), step=0.01, key=f"area_{pid}")

                        col_btn1, col_btn2 = st.columns(2)

                        with col_btn1:
                            if st.form_submit_button("💾 Salvar", use_container_width=True):
                                sucesso, msg = atualizar_processo(pid, novo_num, novo_rt, novo_req, novo_ana, novo_uso, nova_tip, nova_area)
                                if sucesso:
                                    st.success(msg)
                                    del st.session_state[f'editando_{pid}']
                                    st.rerun()
                                else:
                                    st.error(msg)

                        with col_btn2:
                            if st.form_submit_button("❌ Cancelar", use_container_width=True):
                                del st.session_state[f'editando_{pid}']
                                st.rerun()

# ==================== ABA 3: ANÁLISE ====================
with tab3:
    st.header("🤖 Análise com Inteligência Artificial")

    if not api_key:
        st.warning("⚠️ Configure sua API Key na barra lateral")
        st.stop()

    processos = listar_processos()

    if not processos:
        st.info("📭 Cadastre um processo primeiro")
        st.stop()

    # Selecionar processo
    opcoes = [f"{p[1]} - {p[3]}" for p in processos]
    proc_sel = st.selectbox("Selecione o Processo:", opcoes, key="sel_proc")

    if proc_sel:
        num_proc = proc_sel.split(" - ")[0]
        proc_dados = buscar_processo(num_proc)

        if proc_dados:
            # Mostrar dados
            with st.expander("📋 Dados do Processo", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Número", proc_dados[1])
                col2.metric("Uso", proc_dados[5])
                col3.metric("Área", f"{proc_dados[7]}m²")

                st.write(f"**RT:** {proc_dados[2]}")
                st.write(f"**Requerente:** {proc_dados[3]}")

            st.divider()

            # Upload
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📐 PDFs do Projeto")
                projetos = st.file_uploader("Anexe PDFs", type=['pdf'], accept_multiple_files=True, key="pdfs_proj")
                if projetos:
                    st.success(f"✅ {len(projetos)} arquivo(s)")

            with col2:
                st.subheader("📜 PDFs da Legislação")
                legislacoes = st.file_uploader("Anexe PDFs", type=['pdf'], accept_multiple_files=True, key="pdfs_leg")
                if legislacoes:
                    st.success(f"✅ {len(legislacoes)} arquivo(s)")

            st.divider()
            regras = st.text_area("📏 Regras a Verificar:", height=150, placeholder="Ex:\nArt. 10 - Área mínima 50m²")

            st.divider()

            if st.button("🔍 ANALISAR", type="primary", use_container_width=True):
                if not projetos or not legislacoes or not regras:
                    st.error("❌ Anexe os PDFs e digite as regras!")
                else:
                    with st.spinner("🤖 Analisando..."):
                        try:
                            genai.configure(api_key=api_key)

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

                            # Tentar modelos
                            model = None
                            for nome in ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.5-pro']:
                                try:
                                    model = genai.GenerativeModel(nome)
                                    st.info(f"✅ Modelo: {nome}")
                                    break
                                except:
                                    continue

                            if not model:
                                st.error("❌ Nenhum modelo disponível. Verifique sua API Key.")
                                st.stop()

                            # Prompt
                            prompt = f"""Analista da Prefeitura de Contagem.

PROCESSO: {proc_dados[1]}
RT: {proc_dados[2]}
REQUERENTE: {proc_dados[3]}
USO: {proc_dados[5]}
ÁREA: {proc_dados[7]}m²

LEGISLAÇÃO:
{texto_leg[:4000]}

REGRAS:
{regras}

PROJETO:
{texto_proj[:6000]}

Analise:

## ✅ CONFORMIDADES
(cite artigos)

## ❌ NÃO CONFORMIDADES  
(cite artigos)

## ⚠️ PONTOS DE ATENÇÃO

## 🔧 RECOMENDAÇÕES

## 📊 PARECER
APROVADO ou REPROVADO
"""

                            response = model.generate_content(prompt)

                            # Status
                            texto = response.text.upper()
                            if "APROVADO" in texto and "REPROVADO" not in texto:
                                status = "APROVADO"
                                st.success("✅ APROVADO")
                            elif "REPROVADO" in texto:
                                status = "REPROVADO"
                                st.error("❌ REPROVADO")
                            else:
                                status = "INCONCLUSIVO"

                            st.divider()
                            st.markdown(response.text)

                            # Salvar
                            salvar_analise(proc_dados[0], response.text, status)

                            # Download
                            relatorio = f"""PREFEITURA DE CONTAGEM
RELATÓRIO

Processo: {proc_dados[1]}
RT: {proc_dados[2]}
Requerente: {proc_dados[3]}
Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}

{response.text}
"""

                            st.download_button(
                                "📥 BAIXAR",
                                relatorio,
                                f"relatorio_{proc_dados[1].replace('.', '_')}.txt",
                                type="primary"
                            )

                        except Exception as e:
                            st.error(f"❌ Erro: {str(e)}")

st.divider()
st.markdown("🏛️ **Sistema de Validação** • Prefeitura de Contagem")
