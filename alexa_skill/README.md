# JARVIS para Alexa (base da skill)

Esta pasta contém o modelo de interação pt-BR e um handler Lambda inicial. Ainda NÃO é uma skill publicada ou conectada à sua conta Alexa/AWS.

## Antes de publicar
1. Criar uma Custom Skill na Alexa Developer Console, idioma Português (Brasil), invocation name `jarvis celular`.
2. Importar `interaction_model_pt-BR.json` no modelo de interação.
3. Implantar o handler em AWS Lambda com `JARVIS_BRIDGE_URL` apontando para a ponte HTTPS e `JARVIS_API_KEY` igual ao segredo da ponte.
4. **Obrigatório antes de uso real:** trocar o handler de exemplo por uma versão com validação oficial da assinatura da Alexa e validação do application ID usando o Alexa Skills Kit SDK. O handler incluído é demonstrativo e não deve ser publicado como está.
5. Testar na Alexa Developer Console e só então publicar/ativar para a conta.

A skill dispara uma ação permitida no MacroDroid. Ela não dá à Alexa controle geral do Android nem consegue abrir apps por mágica sem o MacroDroid instalado, permissões concedidas e telefone acessível.
