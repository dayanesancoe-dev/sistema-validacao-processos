import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime
import sqlite3

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== BANCO DE DADOS ====================

@st.cache_resource
def init_db():
    conn = sqlite3.connect('processos.db', check_same_thread=False)
    c = conn.cursor()

    # Criar tabela de processos
    c.execute('''CREATE TABLE IF NOT EXISTS processos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        rt TEXT NOT NULL,
        requerente TEXT NOT NULL,
        analista TEXT NOT NULL,
        uso TEXT NOT NULL,
        tipologia TEXT NOT NULL,
        area REAL NOT NULL,
        data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # Criar tabela de análises
    c.execute('''CREATE TABLE IF NOT EXISTS analises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        processo_id INTEGER NOT NULL,
        resultado TEXT NOT NULL,
        status TEXT NOT NULL,
        data_analise DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (processo_id) REFERENCES processos(id)
    )''')

    conn.commit()
    return conn

conn = init_db()

# ==================== FUNÇÕES ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area):
    """Cadastra novo processo"""
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO processos 
                    (numero, rt, requerente, analista, uso, tipologia, area) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (numero, rt, requerente, analista, uso, tipologia, area))
        conn.commit()
        return True, "✅ Processo cadastrado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "❌ Processo já existe!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def listar():
    """Lista todos os processos"""
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY data_cadastro DESC')
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao listar: {str(e)}")
        return []

def deletar(pid):
    """Deleta um processo"""
    try:
        c = conn.cursor()
        c.execute('DELETE FROM analises WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM processos WHERE id = ?', (pid,))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao deletar: {str(e)}")
        return False

def salvar_analise(pid, resultado, status):
    """Salva resultado da análise"""
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO analises (processo_id, resultado, status) 
                    VALUES (?, ?, ?)''', (pid, resultado, status))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar análise: {str(e)}")
        return False

def buscar_analises(pid):
    """Busca análises de um processo"""
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY data_analise DESC', (pid,))
        return c.fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar análises: {str(e)}")
        return []

# ==================== INTERFACE ====================

st.title("🏛️ Sistema de Validação de Processos")
st.markdown("**Prefeitura de Contagem** — Liberação de Alvarás de Construção")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configurações")
    api_key = st.text_input("API Key do Google Gemini:", type="password", 
                            help="Obtenha em: https://aistudio.google.com/app/apikey")

    if api_key:
        st.success("✅ API configurada")
    else:
        st.warning("⚠️ Configure sua API Key")
        st.markdown("[🔗 Obter API Key](https://aistudio.google.com/app/apikey)")

    st.divider()

    # Métricas
    processos_count = len(listar())
    st.metric("Total de Processos", processos_count)

# Abas principais
tab1, tab2, tab3 = st.tabs(["📝 Cadastrar Processo", "📋 Gerenciar Processos", "🤖 Análise com IA"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("📝 Cadastrar Novo Processo")

    with st.form("form_cadastro", clear_on_submit=True):
        st.markdown("### Dados do Processo")

        col1, col2 = st.columns(2)

        with col1:
            num = st.text_input("Número do Processo *", 
                               placeholder="Ex: 2024.001.123",
                               key="cad_num")
            rt = st.text_input("Responsável Técnico *", 
                              placeholder="Nome completo",
                              key="cad_rt")
            req = st.text_input("Requerente *", 
                               placeholder="Nome completo",
                               key="cad_req")
            ana = st.text_input("Analista Responsável *", 
                               placeholder="Nome do analista",
                               key="cad_ana")

        with col2:
            uso = st.selectbox("Uso *", 
                              ["", "Residencial", "Comercial", "Industrial", "Misto", "Institucional", "Outro"],
                              key="cad_uso")
            tip = st.selectbox("Tipologia *", 
                              ["", "Casa", "Sobrado", "Edifício", "Galpão", "Loja", "Sala Comercial", "Outro"],
                              key="cad_tip")
            area = st.number_input("Área Construída (m²) *", 
                                  min_value=0.0, 
                                  step=0.01, 
                                  format="%.2f",
                                  key="cad_area")

        st.markdown("*Campos obrigatórios")

        submitted = st.form_submit_button("✅ Cadastrar Processo", 
                                         type="primary", 
                                         use_container_width=True)

        if submitted:
            if num and rt and req and ana and uso and tip and area > 0:
                sucesso, mensagem = cadastrar(num, rt, req, ana, uso, tip, area)
                if sucesso:
                    st.success(mensagem)
                    st.balloons()
                else:
                    st.error(mensagem)
            else:
                st.error("❌ Por favor, preencha todos os campos obrigatórios!")

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Gerenciar Processos")

    procs = listar()

    if not procs:
        st.info("📭 Nenhum processo cadastrado ainda. Use a aba 'Cadastrar Processo' para adicionar.")
    else:
        st.write(f"**Mostrando {len(procs)} processo(s)**")
        st.divider()

        for p in procs:
            with st.expander(f"📄 Processo {p[1]} - {p[3]}", expanded=False):
                col_info, col_btn = st.columns([4, 1])

                with col_info:
                    st.markdown(f"**Número:** {p[1]}")
                    st.markdown(f"**RT:** {p[2]}")
                    st.markdown(f"**Requerente:** {p[3]}")
                    st.markdown(f"**Analista:** {p[4]}")
                    st.markdown(f"**Uso:** {p[5]} | **Tipologia:** {p[6]}")
                    st.markdown(f"**Área Construída:** {p[7]}m²")
                    st.markdown(f"**Cadastrado em:** {p[8]}")

                    # Buscar análises
                    analises = buscar_analises(p[0])
                    if analises:
                        st.divider()
                        st.markdown("**📊 Histórico de Análises:**")
                        for a in analises:
                            icone = "✅" if a[3] == "APROVADO" else "❌" if a[3] == "REPROVADO" else "⚠️"
                            st.markdown(f"{icone} {a[4]} - **{a[3]}**")

                with col_btn:
                    if st.button("🗑️", key=f"del_btn_{p[0]}", help="Deletar processo"):
                        if deletar(p[0]):
                            st.success("✅ Processo deletado!")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao deletar")

# ==================== ABA 3: ANALISAR ====================
with tab3:
    st.header("🤖 Análise Inteligente com IA")

    if not api_key:
        st.warning("⚠️ Configure sua API Key do Google Gemini na barra lateral para usar esta função")
        st.info("**Como obter:** Acesse https://aistudio.google.com/app/apikey e crie uma chave gratuita")
        st.stop()

    procs = listar()

    if not procs:
        st.info("📭 Você precisa cadastrar pelo menos um processo antes de fazer análises")
        st.stop()

    # Seleção do processo
    proc_sel = st.selectbox("Selecione o Processo para Análise:", 
                           [f"{p[1]} - {p[3]}" for p in procs], 
                           key="anal_proc_sel")

    if proc_sel:
        num_proc = proc_sel.split(" - ")[0]

        # Buscar dados do processo
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (num_proc,))
        dados = c.fetchone()

        if dados:
            # Mostrar dados do processo
            with st.expander("📋 Dados do Processo Selecionado", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Número", dados[1])
                col2.metric("Uso", dados[5])
                col3.metric("Área", f"{dados[7]}m²")

                st.write(f"**RT:** {dados[2]}")
                st.write(f"**Requerente:** {dados[3]}")
                st.write(f"**Analista:** {dados[4]}")
                st.write(f"**Tipologia:** {dados[6]}")

            st.divider()

            # Upload de documentos
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📐 PDFs do Projeto Arquitetônico")
                proj = st.file_uploader("Anexe os PDFs do projeto (plantas, cortes, fachadas)", 
                                       type=['pdf'], 
                                       accept_multiple_files=True, 
                                       key="anal_proj_upload")
                if proj:
                    st.success(f"✅ {len(proj)} arquivo(s) anexado(s)")

            with col2:
                st.subheader("📜 PDFs da Legislação Municipal")
                leg = st.file_uploader("Anexe os PDFs da legislação aplicável", 
                                      type=['pdf'], 
                                      accept_multiple_files=True, 
                                      key="anal_leg_upload")
                if leg:
                    st.success(f"✅ {len(leg)} arquivo(s) anexado(s)")

            st.divider()

            # Regras a verificar
            st.subheader("📏 Regras Específicas da Legislação")
            regras = st.text_area(
                "Digite as regras que devem ser verificadas (uma por linha):",
                height=150,
                key="anal_regras_text",
                placeholder="Exemplo:\nArt. 10 - Área mínima de lote: 50m²\nArt. 15 - Recuo frontal mínimo: 5m\nArt. 20 - Taxa de ocupação máxima: 60%"
            )

            st.divider()

            # Botão de análise
            if st.button("🔍 ANALISAR PROJETO COM INTELIGÊNCIA ARTIFICIAL", 
                        type="primary", 
                        use_container_width=True):

                if not proj:
                    st.error("❌ Anexe pelo menos 1 PDF do projeto arquitetônico!")
                elif not leg:
                    st.error("❌ Anexe pelo menos 1 PDF da legislação municipal!")
                elif not regras:
                    st.error("❌ Digite as regras que devem ser verificadas!")
                else:
                    with st.spinner("🤖 Analisando projeto com Inteligência Artificial... Isso pode levar alguns segundos..."):
                        try:
                            # Configurar Gemini
                            genai.configure(api_key=api_key)

                            # Extrair texto dos PDFs do projeto
                            txt_proj = ""
                            for pdf in proj:
                                reader = PyPDF2.PdfReader(pdf)
                                for page in reader.pages:
                                    txt_proj += page.extract_text() + "\n"

                            # Extrair texto dos PDFs da legislação
                            txt_leg = ""
                            for pdf in leg:
                                reader = PyPDF2.PdfReader(pdf)
                                for page in reader.pages:
                                    txt_leg += page.extract_text() + "\n"

                            # Tentar criar modelo
                            model = None
                            for nome_modelo in ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.5-pro']:
                                try:
                                    model = genai.GenerativeModel(nome_modelo)
                                    st.info(f"✅ Usando modelo: {nome_modelo}")
                                    break
                                except:
                                    continue

                            if not model:
                                st.error("❌ Nenhum modelo do Gemini disponível. Verifique sua API Key.")
                                st.stop()

                            # Criar prompt para análise
                            prompt = f"""Você é um analista técnico especializado em projetos arquitetônicos da Prefeitura de Contagem - MG.

**DADOS DO PROCESSO:**
- Número do Processo: {dados[1]}
- Responsável Técnico: {dados[2]}
- Requerente: {dados[3]}
- Analista: {dados[4]}
- Uso: {dados[5]}
- Tipologia: {dados[6]}
- Área Construída: {dados[7]}m²

**LEGISLAÇÃO MUNICIPAL APLICÁVEL:**
{txt_leg[:4000]}

**REGRAS ESPECÍFICAS A VERIFICAR:**
{regras}

**PROJETO ARQUITETÔNICO SUBMETIDO:**
{txt_proj[:6000]}

**INSTRUÇÕES PARA ANÁLISE:**
Analise detalhadamente o projeto arquitetônico e verifique sua conformidade com a legislação municipal de Contagem.

**IMPORTANTE:**
- SEMPRE cite o artigo específico da legislação
- Seja técnico, objetivo e preciso
- Identifique problemas com localização no projeto quando possível
- Use linguagem formal de parecer técnico

**FORMATO DA RESPOSTA:**

## ✅ CONFORMIDADES
(liste cada item conforme, citando artigo da lei e referência no projeto)

## ❌ NÃO CONFORMIDADES - PONTOS A CORRIGIR
(para cada violação: artigo violado, problema, localização no projeto, correção necessária)

## ⚠️ PONTOS DE ATENÇÃO
(itens que necessitam verificação presencial ou documentação complementar)

## 🔧 RECOMENDAÇÕES TÉCNICAS
(sugestões detalhadas para correção)

## 📊 PARECER TÉCNICO FINAL
Emita parecer conclusivo: **APROVADO** ou **REPROVADO** (justifique tecnicamente citando artigos)
"""

                            # Gerar análise
                            resposta = model.generate_content(prompt)

                            # Determinar status
                            texto_resposta = resposta.text.upper()
                            if "APROVADO" in texto_resposta and "REPROVADO" not in texto_resposta:
                                status = "APROVADO"
                                st.success("✅ PROJETO APROVADO")
                            elif "REPROVADO" in texto_resposta:
                                status = "REPROVADO"
                                st.error("❌ PROJETO REPROVADO")
                            else:
                                status = "INCONCLUSIVO"
                                st.warning("⚠️ ANÁLISE INCONCLUSIVA")

                            st.divider()

                            # Exibir resultado
                            st.markdown(resposta.text)

                            # Salvar análise no banco
                            salvar_analise(dados[0], resposta.text, status)

                            # Preparar relatório para download
                            relatorio = f"""PREFEITURA DE CONTAGEM - MG
RELATÓRIO DE ANÁLISE TÉCNICA DE PROJETO ARQUITETÔNICO

Processo: {dados[1]}
Responsável Técnico: {dados[2]}
Requerente: {dados[3]}
Analista: {dados[4]}
Uso: {dados[5]}
Tipologia: {dados[6]}
Área Construída: {dados[7]}m²
Data da Análise: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

{'='*80}

{resposta.text}

{'='*80}
Relatório gerado automaticamente por Inteligência Artificial (Google Gemini)
Sistema de Validação de Processos - Prefeitura de Contagem
"""

                            st.divider()

                            # Botão de download
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
                            st.info("Verifique se sua API Key está correta e se os PDFs são válidos.")

# Rodapé
st.divider()
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p><strong>🏛️ Sistema de Validação de Processos com Inteligência Artificial</strong></p>
    <p>Prefeitura de Contagem - MG • Setor de Liberação de Alvarás de Construção</p>
    <p style='font-size: 0.85em; color: #666;'>Powered by Google Gemini</p>
</div>
""", unsafe_allow_html=True)
