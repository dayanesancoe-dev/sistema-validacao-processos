import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime

st.set_page_config(page_title="Validação de Projetos", page_icon="🏛️", layout="wide")

st.title("🏛️ Sistema de Validação de Projetos")
st.markdown("**Prefeitura de Contagem** — Análise Inteligente com Google Gemini")

# Configuração API
st.header("⚙️ Configuração")
api_key = st.text_input("Cole sua API Key do Google Gemini:", type="password")

if api_key:
    st.success("✅ API configurada!")

    try:
        genai.configure(api_key=api_key)

        st.divider()
        st.header("📄 Upload de Documentos")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📐 PDFs do Projeto")
            projetos = st.file_uploader("Anexe os PDFs do projeto", type=['pdf'], accept_multiple_files=True, key="proj")
            if projetos:
                st.success(f"✅ {len(projetos)} arquivo(s) anexado(s)")

        with col2:
            st.subheader("📜 PDFs da Legislação")
            legislacoes = st.file_uploader("Anexe os PDFs da legislação", type=['pdf'], accept_multiple_files=True, key="leg")
            if legislacoes:
                st.success(f"✅ {len(legislacoes)} arquivo(s) anexado(s)")

        st.divider()
        st.header("📋 Dados do Processo")

        col1, col2, col3 = st.columns(3)

        with col1:
            numero = st.text_input("Número do Processo", placeholder="Ex: 2024.001")
        with col2:
            requerente = st.text_input("Requerente", placeholder="Nome completo")
        with col3:
            area = st.number_input("Área Total (m²)", min_value=0.0, step=0.1)

        st.divider()
        st.subheader("📏 Regras a Verificar")
        regras = st.text_area(
            "Digite as regras da legislação (uma por linha):", 
            height=150, 
            placeholder="Exemplo:\nArt. 10 - Área mínima de 50m²\nArt. 15 - Recuo frontal de 5m\nArt. 20 - Taxa de ocupação máxima de 60%"
        )

        st.divider()

        if st.button("🔍 ANALISAR COM IA", type="primary", use_container_width=True):
            if projetos and legislacoes and numero and requerente and regras:
                with st.spinner("🤖 Analisando projeto com Inteligência Artificial... Aguarde..."):
                    try:
                        # Extrair texto dos PDFs do projeto
                        texto_proj = ""
                        for idx, pdf in enumerate(projetos, 1):
                            reader = PyPDF2.PdfReader(pdf)
                            for num_pag, page in enumerate(reader.pages, 1):
                                texto_proj += f"\n[PROJETO {idx} - Página {num_pag}]\n"
                                texto_proj += page.extract_text() + "\n"

                        # Extrair texto dos PDFs da legislação
                        texto_leg = ""
                        for idx, pdf in enumerate(legislacoes, 1):
                            reader = PyPDF2.PdfReader(pdf)
                            for num_pag, page in enumerate(reader.pages, 1):
                                texto_leg += f"\n[LEGISLAÇÃO {idx} - Página {num_pag}]\n"
                                texto_leg += page.extract_text() + "\n"

                        # Modelo Gemini atualizado
                        model = genai.GenerativeModel('gemini-1.5-flash')

                        # Prompt para análise
                        prompt = f"""Você é um analista técnico especializado em projetos arquitetônicos da Prefeitura de Contagem - MG.

**DADOS DO PROCESSO:**
- Número: {numero}
- Requerente: {requerente}
- Área Total: {area}m²
- Data da Análise: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

**LEGISLAÇÃO MUNICIPAL:**
{texto_leg[:4500]}

**REGRAS ESPECÍFICAS A VERIFICAR:**
{regras}

**PROJETO ARQUITETÔNICO:**
{texto_proj[:6500]}

**INSTRUÇÕES:**
Analise o projeto e verifique conformidade com a legislação.

**IMPORTANTE:**
- SEMPRE cite o artigo específico da lei
- Seja técnico e objetivo
- Localize problemas no projeto quando possível

**FORMATO DA RESPOSTA:**

## ✅ CONFORMIDADES
Liste o que está conforme, citando artigos da lei.

## ❌ NÃO CONFORMIDADES - PONTOS A CORRIGIR
Para cada violação:
- **Artigo violado:** (número e texto)
- **Problema:** (descrição)
- **Localização:** (onde no projeto)
- **Correção necessária:** (o que fazer)

## ⚠️ PONTOS DE ATENÇÃO
Itens que precisam verificação adicional.

## 🔧 RECOMENDAÇÕES
Sugestões de correção detalhadas.

## 📊 PARECER TÉCNICO FINAL
**APROVADO** ou **REPROVADO** (justifique citando artigos)
"""

                        # Gerar análise
                        response = model.generate_content(prompt)

                        # Exibir resultado
                        st.divider()
                        st.header("📋 RELATÓRIO DE ANÁLISE TÉCNICA")

                        # Verificar status
                        texto_resp = response.text.upper()
                        if "APROVADO" in texto_resp and "REPROVADO" not in texto_resp:
                            st.success("✅ PROJETO APROVADO")
                        elif "REPROVADO" in texto_resp:
                            st.error("❌ PROJETO REPROVADO")
                        else:
                            st.warning("⚠️ ANÁLISE INCONCLUSIVA")

                        st.divider()
                        st.markdown(response.text)

                        # Preparar relatório
                        relatorio = f"""PREFEITURA DE CONTAGEM - MG
RELATÓRIO DE ANÁLISE DE PROJETO ARQUITETÔNICO

Processo: {numero}
Requerente: {requerente}
Área Total: {area}m²
Data: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

Documentos Analisados:
- Projeto: {len(projetos)} arquivo(s) PDF
- Legislação: {len(legislacoes)} arquivo(s) PDF

Regras Verificadas:
{regras}

{'='*80}

{response.text}

{'='*80}
Relatório gerado por IA (Google Gemini 1.5 Flash)
Sistema de Validação - Prefeitura de Contagem
"""

                        # Download
                        st.divider()
                        st.download_button(
                            label="📥 BAIXAR RELATÓRIO COMPLETO",
                            data=relatorio,
                            file_name=f"relatorio_{numero.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain",
                            use_container_width=True,
                            type="primary"
                        )

                    except Exception as e:
                        st.error(f"❌ Erro na análise: {str(e)}")
                        st.info("Verifique se sua API Key está correta e se os PDFs são válidos.")
            else:
                st.error("❌ Preencha todos os campos e anexe os PDFs!")

    except Exception as e:
        st.error(f"❌ Erro ao configurar API: {str(e)}")

else:
    st.info("👆 Cole sua API Key do Google Gemini acima para começar")
    st.markdown("[🔗 Obter API Key gratuitamente](https://aistudio.google.com/app/apikey)")

    with st.expander("❓ Como obter a API Key?"):
        st.markdown("""
        **Passo a passo:**
        1. Acesse: https://aistudio.google.com/app/apikey
        2. Faça login com sua conta Google
        3. Clique em **"Get API Key"** ou **"Create API key"**
        4. Escolha **"Create API key in new project"**
        5. Copie a chave gerada (começa com AIza...)
        6. Cole no campo acima
        """)

st.divider()
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p><strong>🏛️ Sistema de Validação com Inteligência Artificial</strong></p>
    <p>Prefeitura de Contagem - MG</p>
    <p style='font-size: 0.85em; color: #666;'>Powered by Google Gemini 1.5 Flash</p>
</div>
""", unsafe_allow_html=True)
