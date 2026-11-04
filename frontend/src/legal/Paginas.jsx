// Política de Privacidade e Termos de Uso (abrem sem sessão: /privacidade e /termos).
// Versão inicial, escrita a partir do que o site guarda de facto; deve ser revista
// por um advogado antes do lançamento ao público.
import { ATUALIZADO_EM, CNPJ, COMISSAO_SITE as COMISSAO, EMAIL_CONTATO, RESPONSAVEL } from "./dados";

const identificacao = CNPJ ? `${RESPONSAVEL}, CNPJ ${CNPJ}` : RESPONSAVEL;

function Pagina({ titulo, children, onVoltar }) {
  return (
    <div className="legal-page">
      <article className="legal-card">
        <header>
          <p className="legal-marca">Radar Leilão</p>
          <h1>{titulo}</h1>
          <p className="legal-data">Última atualização: {ATUALIZADO_EM}</p>
        </header>
        {children}
        <footer className="legal-rodape">
          <button type="button" className="login-alternar" onClick={onVoltar}>
            Voltar ao site
          </button>
        </footer>
      </article>
    </div>
  );
}

const contato = <a href={`mailto:${EMAIL_CONTATO}`}>{EMAIL_CONTATO}</a>;

export function PoliticaPrivacidade({ onVoltar }) {
  return (
    <Pagina titulo="Política de Privacidade" onVoltar={onVoltar}>
      <p>
        Esta política explica que dados pessoais o Radar Leilão trata, para quê, com quem são
        compartilhados e como você pode exercer os seus direitos, de acordo com a Lei Geral de
        Proteção de Dados (Lei nº 13.709/2018, LGPD).
      </p>

      <h2>1. Quem é o responsável</h2>
      <p>
        O controlador dos dados é {identificacao}, pessoa jurídica responsável pelo Radar Leilão.
        Para qualquer assunto sobre os seus dados, escreva para {contato}.
      </p>

      <h2>2. Que dados tratamos</h2>
      <ul>
        <li><strong>Conta:</strong> nome, e-mail e senha. A senha nunca é guardada em texto: só uma versão cifrada (hash) que não permite recuperá-la.</li>
        <li><strong>Pedido de conta de corretor:</strong> CRECI, nome profissional, telefone e imobiliária, se os informar.</li>
        <li><strong>O que você cria no site:</strong> alertas de oportunidades, simulações de rentabilidade, oportunidades, negociações, operações e as observações que escrever nelas.</li>
        <li><strong>Anúncios que publicar:</strong> os dados do imóvel, valores, fotos e a data em que aceitou a comissão do site.</li>
        <li><strong>Notificações e e-mails:</strong> as novidades dos seus alertas e a data em que enviamos o resumo por e-mail.</li>
        <li><strong>Recuperação de senha:</strong> um código de uso único, guardado apenas na forma cifrada e válido por 1 hora.</li>
        <li><strong>Perguntas à seção "Dúvidas sobre leilão":</strong> o texto das perguntas e respostas da conversa é enviado ao serviço de inteligência artificial que gera a resposta (ver item 4). Não guardamos essas conversas na nossa base.</li>
        <li><strong>Registros técnicos:</strong> o provedor de hospedagem registra dados técnicos dos acessos (como endereço IP, data e hora e página pedida), para segurança e funcionamento.</li>
      </ul>
      <p>Não pedimos CPF, dados bancários nem documentos de identidade.</p>

      <h2>3. Para que usamos e com que base legal</h2>
      <ul>
        <li><strong>Prestar o serviço que você pediu</strong> (criar a conta, mostrar os imóveis, guardar alertas e simulações, aprovar contas de corretor, recuperar a senha): execução de contrato (art. 7º, V, da LGPD).</li>
        <li><strong>Enviar os resumos dos seus alertas por e-mail:</strong> execução de contrato. Você pode desligá-los a qualquer momento na página de Alertas ou pelo link no próprio e-mail.</li>
        <li><strong>Segurança e prevenção de abusos</strong> (limites de tentativas de login e de pedidos, registros técnicos): legítimo interesse (art. 7º, IX).</li>
        <li><strong>Cumprir obrigações legais ou pedidos de autoridades:</strong> art. 7º, II.</li>
      </ul>
      <p>Não vendemos dados pessoais nem os usamos para publicidade de terceiros.</p>

      <h2>4. Com quem compartilhamos</h2>
      <ul>
        <li><strong>Render</strong> (hospedagem do site e da base de dados).</li>
        <li><strong>Brevo</strong> (envio de e-mails: recuperação de senha e resumos de alertas). Recebe o seu nome, e-mail e o conteúdo da mensagem.</li>
        <li><strong>Anthropic</strong> (serviço de inteligência artificial usado na seção "Dúvidas sobre leilão"). Recebe o texto das perguntas que você fizer; evite escrever dados pessoais nessas perguntas.</li>
        <li><strong>Outros usuários, só quando necessário:</strong> numa oportunidade, o corretor atribuído e o cliente veem os dados um do outro necessários para o atendimento (como nome e e-mail).</li>
        <li><strong>Anúncios publicados:</strong> depois de aprovados, os dados do imóvel e as fotos ficam visíveis a quem usa o site; o seu nome e contato não aparecem no anúncio.</li>
        <li><strong>Caixa Econômica Federal:</strong> as fotos dos imóveis são carregadas diretamente do site da Caixa pelo seu navegador, que por isso fica sabendo o seu endereço IP, como em qualquer visita ao site da Caixa. Não enviamos à Caixa nenhum dado da sua conta.</li>
      </ul>

      <h2>5. Transferência internacional</h2>
      <p>
        Render, Brevo e Anthropic guardam ou tratam dados em servidores fora do Brasil (por exemplo,
        nos Estados Unidos ou na Europa). Essa transferência é feita para prestar o serviço que você
        pediu e com fornecedores que adotam medidas de proteção de dados, nos termos do art. 33 da LGPD.
      </p>

      <h2>6. Armazenamento no seu navegador</h2>
      <p>
        O site guarda no seu navegador (armazenamento local) a sua sessão de acesso e a lista de
        imóveis favoritos. Não usamos cookies de publicidade nem ferramentas de rastreamento de terceiros.
        Ao sair da conta, a sessão é apagada.
      </p>

      <h2>7. Por quanto tempo guardamos</h2>
      <ul>
        <li>Dados da conta e o que você criou no site: enquanto a conta existir.</li>
        <li>Se você apagar a conta no site (botão "Apagar a minha conta", em Meu perfil), ela e os dados ligados a ela são apagados na hora. Se pedir por e-mail, apagamos em até 30 dias. Em ambos os casos, salvo o que a lei obrigar a guardar.</li>
        <li>Códigos de recuperação de senha: deixam de valer após 1 hora ou após o uso.</li>
        <li>Registros técnicos: pelo tempo definido pelo provedor de hospedagem e pela lei.</li>
      </ul>

      <h2>8. Os seus direitos</h2>
      <p>
        Você pode pedir, a qualquer momento: confirmação de que tratamos os seus dados; acesso a eles;
        correção de dados incompletos ou errados; anonimização, bloqueio ou eliminação de dados
        desnecessários; portabilidade; informação sobre com quem os compartilhamos; eliminação dos
        dados e da conta; e revisão de decisões tomadas apenas de forma automatizada (art. 18 da LGPD).
      </p>
      <p>
        Para apagar a conta e os seus dados, você pode usar o botão "Apagar a minha conta" em Meu
        perfil, que confirma com a sua senha. Para os outros direitos (ou se preferir), escreva para
        {" "}{contato} a partir do e-mail da sua conta. Respondemos em até 15 dias. Você também pode apresentar reclamação à Autoridade
        Nacional de Proteção de Dados (ANPD).
      </p>

      <h2>9. Segurança</h2>
      <p>
        Usamos conexão criptografada (HTTPS), senhas guardadas apenas na forma cifrada, sessões com prazo
        de validade e acesso restrito à base de dados. Nenhum sistema é totalmente seguro; se houver
        um incidente que possa causar risco relevante, avisaremos os afetados e a ANPD.
      </p>

      <h2>10. Menores de idade</h2>
      <p>O Radar Leilão destina-se a maiores de 18 anos e não coleta, de propósito, dados de menores.</p>

      <h2>11. Alterações desta política</h2>
      <p>
        Podemos atualizar esta política. A data no topo mostra a última versão; mudanças relevantes
        serão avisadas no site ou por e-mail.
      </p>
    </Pagina>
  );
}

export function TermosUso({ onVoltar }) {
  return (
    <Pagina titulo="Termos de Uso" onVoltar={onVoltar}>
      <p>
        Estes termos regulam o uso do Radar Leilão. Ao criar uma conta ou usar o site, você concorda
        com eles e com a <a href="/privacidade">Política de Privacidade</a>.
      </p>

      <h2>1. O que é o Radar Leilão</h2>
      <p>
        O Radar Leilão reúne e organiza informações públicas sobre imóveis vendidos pela Caixa
        Econômica Federal em leilão, com cálculos de desconto, alertas e ferramentas de análise.
        <strong> O Radar Leilão não tem qualquer ligação com a Caixa</strong> e não vende imóveis:
        a compra é feita diretamente nos canais oficiais da Caixa ou do leiloeiro.
      </p>

      <h2>2. As informações podem estar desatualizadas</h2>
      <p>
        Datas, valores, descontos, fotos e condições vêm das listas e editais publicados pela Caixa e
        podem mudar a qualquer momento ou conter erros. <strong>Antes de qualquer decisão, confirme
        sempre no edital e no site oficial da Caixa.</strong> Os cálculos de desconto, economia,
        pontuação e rentabilidade são estimativas para ajudar na análise, não garantias.
      </p>

      <h2>3. Não é assessoria jurídica nem financeira</h2>
      <p>
        O conteúdo do site, incluindo as respostas da seção "Dúvidas sobre leilão" (geradas por
        inteligência artificial), é apenas informativo e pode conter erros. Não substitui a orientação
        de um advogado, corretor ou outro profissional habilitado.
      </p>

      <h2>4. A sua conta</h2>
      <ul>
        <li>Você precisa ter pelo menos 18 anos e informar dados verdadeiros.</li>
        <li>A conta é pessoal; guarde a sua senha e avise-nos se suspeitar de uso indevido.</li>
        <li>Você é responsável pelo que fizer com a sua conta.</li>
      </ul>

      <h2>5. Anúncios e corretores</h2>
      <p>
        Qualquer usuário com conta pode anunciar um imóvel. Quem anuncia declara ter direito de o
        vender ou autorização para o anunciar, e é responsável pela veracidade das informações, valores
        e fotos. Cada anúncio é revisto por um administrador antes de aparecer no site; podemos recusar,
        pedir correções ou retirar anúncios incompletos, falsos ou que violem estes termos.
      </p>
      <p>
        Contas de corretor exigem CRECI válido e aprovação. O corretor é responsável pela sua atuação
        profissional e pelo cumprimento das regras do seu conselho profissional. Podemos recusar ou
        retirar a aprovação se houver dados falsos ou abuso.
      </p>

      <h2>6. Usos proibidos</h2>
      <ul>
        <li>Coletar dados do site de forma automatizada (robôs, raspagem) sem autorização.</li>
        <li>Tentar acessar contas ou dados de outras pessoas, ou prejudicar o funcionamento do site.</li>
        <li>Publicar conteúdo falso, ilegal ou que viole direitos de terceiros.</li>
      </ul>

      <h2>7. Preço e comissão sobre vendas</h2>
      <p>
        Pesquisar imóveis, criar alertas e anunciar no Radar Leilão é gratuito.
      </p>
      <p>
        <strong>Comissão do site:</strong> quem anuncia um imóvel aceita pagar ao Radar Leilão uma
        comissão de <strong>{COMISSAO}% sobre o valor final de venda</strong>, se a venda for feita a
        um comprador que chegou ao imóvel pelo site (por exemplo, por ter demonstrado interesse no
        anúncio). A comissão é paga pelo vendedor quando o negócio fechar; a forma e o prazo de
        pagamento são combinados nessa altura. A aceitação fica registada, com a data, quando o
        anúncio é enviado.
      </p>
      <p>
        Poderemos lançar outras funcionalidades ou planos pagos; nesse caso, preço, forma de pagamento
        e condições de cancelamento serão informados antes de qualquer cobrança, e nada será cobrado
        sem a sua aceitação expressa.
      </p>

      <h2>8. Responsabilidade</h2>
      <p>
        As decisões de participar de um leilão e de comprar um imóvel são suas. Na medida permitida
        pela lei, o Radar Leilão não responde por prejuízos resultantes de informações desatualizadas
        ou erradas vindas das fontes públicas, de indisponibilidade temporária do site ou de decisões
        tomadas com base nas estimativas. Nada nestes termos afasta os direitos que o Código de Defesa
        do Consumidor lhe garante.
      </p>

      <h2>9. Propriedade intelectual</h2>
      <p>
        O site, o seu código, marca e textos pertencem a {RESPONSAVEL}. As informações
        dos imóveis e as fotos pertencem às respectivas fontes (como a Caixa).
      </p>

      <h2>10. Suspensão e encerramento</h2>
      <p>
        Você pode encerrar a sua conta a qualquer momento, pelo botão "Apagar a minha conta" em Meu
        perfil ou pedindo por {contato}. Podemos suspender
        contas que violem estes termos. Também podemos alterar ou descontinuar o serviço, avisando com
        antecedência razoável sempre que possível.
      </p>

      <h2>11. Alterações destes termos</h2>
      <p>
        Podemos atualizar estes termos. A data no topo mostra a última versão; mudanças relevantes
        serão avisadas no site ou por e-mail, e continuar a usar o site depois disso significa aceitá-las.
      </p>

      <h2>12. Lei e foro</h2>
      <p>
        Estes termos seguem as leis do Brasil. Fica eleito o foro do domicílio do usuário, conforme o
        Código de Defesa do Consumidor.
      </p>

      <h2>13. Contato</h2>
      <p>Responsável: {identificacao}. Dúvidas sobre estes termos: {contato}.</p>
    </Pagina>
  );
}
