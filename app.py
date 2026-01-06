import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, timedelta
import sqlite3
import os

st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# ==================== BANCO DE DADOS ====================

def reset_database():
    """Reseta o banco"""
    if os.path.exists('processos.db'):
        os.remove('processos.db')
    return init_db()

@st.cache_resource
def init_db():
    """Inicializa banco"""
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()

        # Tabela processos
        c.execute('''CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            rt TEXT NOT NULL,
            requerente TEXT NOT NULL,
            analista TEXT NOT NULL,
            uso TEXT NOT NULL,
            tipologia TEXT NOT NULL,
            area REAL NOT NULL,
            data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Tabela análises
        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            status TEXT NOT NULL,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        # Tabela tramitação
        c.execute('''CREATE TABLE IF NOT EXISTS tramitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER NOT NULL,
            setor TEXT NOT NULL,
            data_entrada TEXT NOT NULL,
            data_saida TEXT,
            observacao TEXT,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')

        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Erro ao inicializar: {str(e)}")
        return None

conn = init_db()

# ==================== FUNÇÕES ====================

def cadastrar(numero, rt, requerente, analista, uso, tipologia, area):
    """Cadastra processo"""
    if not conn:
        return False, "❌ Erro de conexão!"
    try:
        c = conn.cursor()
        c.execute('''INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (numero, rt, requerente, analista, uso, tipologia, area))
        conn.commit()
        return True, "✅ Cadastrado!"
    except sqlite3.IntegrityError:
        return False, "❌ Processo já existe!"
    except Exception as e:
        return False, f"❌ Erro: {str(e)}"

def listar():
    """Lista processos"""
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos ORDER BY id DESC')
        return c.fetchall()
    except:
        return []

def buscar_por_numero(numero):
    """Busca processo"""
    if not conn:
        return None
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM processos WHERE numero = ?', (numero,))
        return c.fetchone()
    except:
        return None

def deletar(pid):
    """Deleta processo"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('DELETE FROM analises WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM tramitacao WHERE processo_id = ?', (pid,))
        c.execute('DELETE FROM processos WHERE id = ?', (pid,))
        conn.commit()
        return True
    except:
        return False

def salvar_analise(pid, resultado, status):
    """Salva análise"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        c.execute('INSERT INTO analises (processo_id, resultado, status) VALUES (?, ?, ?)', 
                 (pid, resultado, status))
        conn.commit()
        return True
    except:
        return False

def buscar_analises(pid):
    """Busca análises"""
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('SELECT * FROM analises WHERE processo_id = ? ORDER BY id DESC', (pid,))
        return c.fetchall()
    except:
        return []

# ==================== FUNÇÕES TRAMITAÇÃO ====================

def adicionar_tramitacao(processo_id, setor, data_entrada, observacao=""):
    """Adiciona movimentação"""
    if not conn:
        return False
    try:
        c = conn.cursor()
        # Fechar tramitação anterior (se houver)
        c.execute('''UPDATE tramitacao 
                    SET data_saida = ? 
                    WHERE processo_id = ? AND data_saida IS NULL''',
                 (data_entrada, processo_id))

        # Adicionar nova
        c.execute('''INSERT INTO tramitacao (processo_id, setor, data_entrada, observacao) 
                    VALUES (?, ?, ?, ?)''',
                 (processo_id, setor, data_entrada, observacao))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro: {str(e)}")
        return False

def listar_tramitacao(processo_id):
    """Lista tramitações"""
    if not conn:
        return []
    try:
        c = conn.cursor()
        c.execute('''SELECT * FROM tramitacao 
                    WHERE processo_id = ? 
                    ORDER BY data_entrada DESC''', (processo_id,))
        return c.fetchall()
    except:
        return []

def calcular_tempo(data_entrada, data_saida):
    """Calcula tempo em dias"""
    try:
        entrada = datetime.strptime(data_entrada, '%Y-%m-%d')
        if data_saida:
            saida = datetime.strptime(data_saida, '%Y-%m-%d')
        else:
            saida = datetime.now()
        diff = (saida - entrada).days
        return diff
    except:
        return 0

def estatisticas_tramitacao(processo_id):
    """Estatísticas por setor"""
    tramitacoes = listar_tramitacao(processo_id)
    if not tramitacoes:
        return {}

    stats = {}
    for t in tramitacoes:
        setor = t[2]
        tempo = calcular_tempo(t[3], t[4])
        if setor not in stats:
            stats[setor] = 0
        stats[setor] += tempo

    return stats

# ==================== INTERFACE ====================

st.title("🏛️ Sistema de Validação de Processos")
st.markdown("**Prefeitura de Contagem** — Setor de Liberação de Alvarás")

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
    st.metric("Total de Processos", len(listar()))

    st.divider()
    if st.button("🔄 Resetar Banco de Dados", help="Use apenas se houver erros no banco"):
        reset_database()
        st.success("✅ Banco resetado!")
        st.rerun()

# Abas principais
tab1, tab2, tab3, tab4 = st.tabs(["📝 Cadastrar", "📋 Gerenciar", "🔄 Tramitação", "🤖 Analisar"])

# ==================== ABA 1: CADASTRAR ====================
with tab1:
    st.header("📝 Cadastrar Novo Processo")

    with st.form("form_cad"):
        col1, col2 = st.columns(2)

        with col1:
            num = st.text_input("Número do Processo *", placeholder="Ex: 2024.001.123")
            rt = st.text_input("Responsável Técnico *", placeholder="Nome do RT")
            req = st.text_input("Requerente *", placeholder="Nome do requerente")
            ana = st.text_input("Analista *", placeholder="Nome do analista")

        with col2:
            uso = st.selectbox("Uso *", [
                "",
                "Unifamiliar",
                "Multifamiliar",
                "Serviços",
                "Comércio Varejista",
                "Comércio Atacadista",
                "Indústria",
                "Misto",
                "Sem destinação específica"
            ])

            tip = st.selectbox("Tipologia *", [
                "",
                "Aprovação Inicial",
                "Levantamento Existente",
                "Modificação de Projeto",
                "Regularização",
                "Misto",
                "RIU",
                "ERB",
                "As Built"
            ])

            area = st.number_input("Área Construída (m²) *", min_value=0.0, step=0.01, format="%.2f")

        st.markdown("*Campos obrigatórios")

        if st.form_submit_button("✅ Cadastrar Processo", type="primary", use_container_width=True):
            if num and rt and req and ana and uso and tip and area > 0:
                ok, msg = cadastrar(num, rt, req, ana, uso, tip, area)
                if ok:
                    st.success(msg)
                    # Adicionar primeira tramitação
                    processo = buscar_por_numero(num)
                    if processo:
                        adicionar_tramitacao(processo[0], "Protocolo", datetime.now().strftime('%Y-%m-%d'), "Cadastro inicial")
                    st.balloons()
                else:
                    st.error(msg)
            else:
                st.error("❌ Preencha todos os campos obrigatórios!")

# ==================== ABA 2: GERENCIAR ====================
with tab2:
    st.header("📋 Gerenciar Processos")

    procs = listar()

    if not procs:
        st.info("📭 Nenhum processo cadastrado ainda")
    else:
        st.write(f"**Total: {len(procs)} processo(s) cadastrado(s)**")
        st.divider()

        for p in procs:
            with st.expander(f"📄 Processo {p[1]} - {p[3]}"):
                col_info, col_btn = st.columns([4, 1])

                with col_info:
                    st.write(f"**Número:** {p[1]}")
                    st.write(f"**RT:** {p[2]}")
                    st.write(f"**Requerente:** {p[3]}")
                    st.write(f"**Analista:** {p[4]}")
                    st.write(f"**Uso:** {p[5]}")
                    st.write(f"**Tipologia:** {p[6]}")
                    st.write(f"**Área:** {p[7]}m²")
                    st.write(f"**Cadastrado em:** {p[8]}")

                    # Análises
                    analises = buscar_analises(p[0])
                    if analises:
                        st.divider()
                        st.write("**📊 Histórico de Análises:**")
                        for a in analises:
                            icone = "✅" if a[3] == "APROVADO" else "❌" if a[3] == "REPROVADO" else "⚠️"
                            st.write(f"{icone} {a[4]} - **{a[3]}**")

                with col_btn:
                    if st.button("🗑️", key=f"del_{p[0]}", help="Deletar processo"):
                        if deletar(p[0]):
                            st.success("✅ Processo deletado!")
                            st.rerun()
                        else:
                            st.error("❌ Erro ao deletar")

# ==================== ABA 3: TRAMITAÇÃO ====================
with tab3:
    st.header("🔄 Gestão de Tramitação")

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo primeiro na aba 'Cadastrar'")
    else:
        # Seleção do processo
        proc_sel = st.selectbox("Selecione o Processo:", 
                               [f"{p[1]} - {p[3]}" for p in procs], 
                               key="tram_sel")

        if proc_sel:
            num_proc = proc_sel.split(" - ")[0]
            processo = buscar_por_numero(num_proc)

            if processo:
                st.divider()

                # Adicionar nova movimentação
                st.subheader("➕ Registrar Nova Movimentação")

                col1, col2, col3 = st.columns(3)

                with col1:
                    setor_opcoes = [
                        "Requerente",
                        "Analista",
                        "Fiscalização",
                        "Parecer Externo",
                        "Emissão de Alvará",
                        "Protocolo",
                        "Arquivo"
                    ]
                    setor = st.selectbox("Setor Responsável:", setor_opcoes, key="tram_setor")

                with col2:
                    data_mov = st.date_input("Data da Movimentação:", key="tram_data")

                with col3:
                    obs = st.text_input("Observação:", key="tram_obs", placeholder="Ex: Retornou para correções")

                if st.button("✅ Registrar Movimentação", type="primary", use_container_width=True):
                    if adicionar_tramitacao(processo[0], setor, data_mov.strftime('%Y-%m-%d'), obs):
                        st.success("✅ Movimentação registrada com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Erro ao registrar movimentação")

                st.divider()

                # Histórico
                st.subheader("📊 Histórico de Tramitação")

                tramitacoes = listar_tramitacao(processo[0])

                if tramitacoes:
                    # Criar tabela de histórico
                    for t in tramitacoes:
                        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

                        with col1:
                            # Ícones por setor
                            icones_setor = {
                                "Requerente": "👤",
                                "Analista": "👨‍💼",
                                "Fiscalização": "🔍",
                                "Parecer Externo": "📋",
                                "Emissão de Alvará": "✅",
                                "Protocolo": "📥",
                                "Arquivo": "📁"
                            }
                            icone = icones_setor.get(t[2], "📌")
                            st.write(f"{icone} **{t[2]}**")

                        with col2:
                            entrada = datetime.strptime(t[3], '%Y-%m-%d').strftime('%d/%m/%Y')
                            st.write(f"📥 {entrada}")

                        with col3:
                            if t[4]:
                                saida = datetime.strptime(t[4], '%Y-%m-%d').strftime('%d/%m/%Y')
                                st.write(f"📤 {saida}")
                            else:
                                st.write("🔄 **Em andamento**")

                        with col4:
                            tempo = calcular_tempo(t[3], t[4])
                            st.metric("Dias", tempo)

                        if t[5]:
                            st.caption(f"💬 {t[5]}")

                        st.divider()

                    # Estatísticas por setor
                    st.subheader("📈 Tempo por Setor")

                    stats = estatisticas_tramitacao(processo[0])

                    if stats:
                        # Criar colunas para as métricas
                        num_cols = len(stats)
                        cols = st.columns(num_cols if num_cols > 0 else 1)

                        for idx, (setor, dias) in enumerate(stats.items()):
                            with cols[idx % num_cols]:
                                st.metric(setor, f"{dias} dias")

                        # Tempo total
                        total_dias = sum(stats.values())
                        st.divider()
                        st.metric("⏱️ **Tempo Total do Processo**", f"{total_dias} dias")
                else:
                    st.info("📭 Nenhuma movimentação registrada para este processo")

# ==================== ABA 4: ANALISAR ====================
with tab4:
    st.header("🤖 Análise Inteligente com IA")

    if not api_key:
        st.warning("⚠️ Configure sua API Key do Google Gemini na barra lateral")
        st.info("**Como obter:** Acesse https://aistudio.google.com/app/apikey e crie uma chave gratuita")
        st.stop()

    procs = listar()

    if not procs:
        st.info("📭 Cadastre um processo primeiro na aba 'Cadastrar'")
        st.stop()

    proc_sel = st.selectbox("Selecione o Processo para Análise:", 
                           [f"{p[1]} - {p[3]}" for p in procs], 
                           key="anal_sel")

    if proc_sel:
        num_proc = proc_sel.split(" - ")[0]
        dados = buscar_por_numero(num_proc)

        if dados:
            # Mostrar dados do processo
            with st.expander("📋 Dados do Processo", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Número", dados[1])
                col2.metric("Uso", dados[5])
                col3.metric("Área", f"{dados[7]}m²")

                st.write(f"**RT:** {dados[2]}")
                st.write(f"**Requerente:** {dados[3]}")
                st.write(f"**Analista:** {dados[4]}")
                st.write(f"**Tipologia:** {dados[6]}")

            st.divider()

            # Upload de arquivos
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📐 PDFs do Projeto")
                proj = st.file_uploader(
                    "Anexe os PDFs do projeto arquitetônico (plantas, cortes, fachadas)", 
                    type=['pdf'], 
                    accept_multiple_files=True, 
                    key="proj"
                )
                if proj:
                    st.success(f"✅ {len(proj)} arquivo(s) anexado(s)")

            with col2:
                st.subheader("📜 PDFs da Legislação")
                leg = st.file_uploader(
                    "Anexe os PDFs da legislação municipal aplicável", 
                    type=['pdf'], 
                    accept_multiple_files=True, 
                    key="leg"
                )
                if leg:
                    st.success(f"✅ {len(leg)} arquivo(s) anexado(s)")

            st.divider()

            st.subheader("📏 Regras da Legislação a Verificar")
            regras = st.text_area(
                "Digite as regras específicas que devem ser verificadas (uma por linha):", 
                height=150, 
                placeholder="Exemplo:\nArt. 10 - Área mínima de lote: 50m²\nArt. 15 - Recuo frontal mínimo: 5m\nArt. 20 - Taxa de ocupação máxima: 60%",
                key="regras_anal"
            )

            st.divider()

            if st.button("🔍 ANALISAR PROJETO COM INTELIGÊNCIA ARTIFICIAL", type="primary", use_container_width=True):
                if not proj:
                    st.error("❌ Anexe pelo menos 1 PDF do projeto!")
                elif not leg:
                    st.error("❌ Anexe pelo menos 1 PDF da legislação!")
                elif not regras:
                    st.error("❌ Digite as regras que devem ser verificadas!")
                else:
                    with st.spinner("🤖 Analisando projeto com Inteligência Artificial... Aguarde..."):
                        try:
                            # Configurar API
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
                            for nome in ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.5-pro']:
                                try:
                                    model = genai.GenerativeModel(nome)
                                    st.info(f"✅ Usando modelo: {nome}")
                                    break
                                except:
                                    continue

                            if not model:
                                st.error("❌ Nenhum modelo do Gemini disponível. Verifique sua API Key.")
                                st.stop()

                            # Criar prompt para análise
                            prompt = f"""Você é um analista técnico especializado em projetos arquitetônicos da Prefeitura de Contagem - MG.

**DADOS DO PROCESSO:**
- Número: {dados[1]}
- RT: {dados[2]}
- Requerente: {dados[3]}
- Analista: {dados[4]}
- Uso: {dados[5]}
- Tipologia: {dados[6]}
- Área: {dados[7]}m²

**LEGISLAÇÃO MUNICIPAL:**
{txt_leg[:4000]}

**REGRAS ESPECÍFICAS A VERIFICAR:**
{regras}

**PROJETO ARQUITETÔNICO:**
{txt_proj[:6000]}

**INSTRUÇÕES:**
Analise detalhadamente o projeto e verifique conformidade com a legislação.
SEMPRE cite o artigo específico da lei.

**FORMATO DA RESPOSTA:**

## ✅ CONFORMIDADES
(liste o que está conforme, citando artigos)

## ❌ NÃO CONFORMIDADES
(liste violações, citando artigos e localizando no projeto)

## ⚠️ PONTOS DE ATENÇÃO
(itens que precisam verificação adicional)

## 🔧 RECOMENDAÇÕES
(sugestões de correção)

## 📊 PARECER TÉCNICO FINAL
APROVADO ou REPROVADO (justifique citando artigos)
"""

                            # Gerar análise
                            resp = model.generate_content(prompt)

                            # Determinar status
                            texto = resp.text.upper()
                            if "APROVADO" in texto and "REPROVADO" not in texto:
                                status = "APROVADO"
                                st.success("✅ PROJETO APROVADO")
                            elif "REPROVADO" in texto:
                                status = "REPROVADO"
                                st.error("❌ PROJETO REPROVADO")
                            else:
                                status = "INCONCLUSIVO"
                                st.warning("⚠️ ANÁLISE INCONCLUSIVA")

                            st.divider()
                            st.markdown(resp.text)

                            # Salvar análise
                            salvar_analise(dados[0], resp.text, status)

                            # Preparar relatório
                            rel = f"""PREFEITURA DE CONTAGEM - MG
RELATÓRIO DE ANÁLISE TÉCNICA

Processo: {dados[1]}
RT: {dados[2]}
Requerente: {dados[3]}
Analista: {dados[4]}
Uso: {dados[5]}
Tipologia: {dados[6]}
Área: {dados[7]}m²
Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}

{'='*80}

{resp.text}

{'='*80}
Relatório gerado por IA (Google Gemini)
Sistema de Validação - Prefeitura de Contagem
"""

                            st.divider()
                            st.download_button(
                                "📥 BAIXAR RELATÓRIO COMPLETO",
                                rel,
                                f"relatorio_{dados[1].replace('.', '_')}.txt",
                                type="primary",
                                use_container_width=True
                            )

                        except Exception as e:
                            st.error(f"❌ Erro durante a análise: {str(e)}")

# Rodapé
st.divider()
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p><strong>🏛️ Sistema de Validação de Processos</strong></p>
    <p>Prefeitura de Contagem - MG • Setor de Liberação de Alvarás</p>
    <p style='font-size: 0.85em; color: #666;'>Powered by Google Gemini</p>
</div>
""", unsafe_allow_html=True)
