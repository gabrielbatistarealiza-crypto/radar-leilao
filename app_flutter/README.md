# Radar Leilão — aplicativo Flutter

Este diretório contém o aplicativo móvel Android/iOS separado do painel administrativo React em `../frontend`. A API permanece no FastAPI em `../backend`.

## Executar no Android

O projeto Flutter e as pastas nativas `android/` e `ios/` já foram gerados. O login envia `email` e `senha` a `POST /login`; após autenticar, o app carrega imóveis de `GET /imoveis/` em páginas de 10 resultados e permite carregar as páginas seguintes. A tela inicial permite buscar nos imóveis carregados, filtrar por cidade, estado, preço máximo e desconto mínimo e ordenar pelos campos disponíveis na API. Os filtros de leilão usam o parâmetro `status_leilao` do endpoint.

Com a API FastAPI em execução na mesma máquina, o endereço padrão `http://10.0.2.2:8000` alcança o host a partir do emulador Android. A permissão de internet está declarada e o tráfego HTTP está habilitado somente no manifesto de depuração.

```powershell
flutter doctor
flutter pub get
flutter run -d emulator-5554
```

Para um dispositivo físico, use o endereço da API acessível na rede local:

```powershell
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000
```

O endereço base também pode ser configurado por `--dart-define=API_BASE_URL=...`. No iOS Simulator, use `http://localhost:8000`; as pastas iOS estão presentes, mas compilar ou executar iOS requer macOS com Xcode. Builds publicados devem usar HTTPS. O Firebase não foi integrado nesta etapa.

## Preparação de release Android

O tipo `release` não usa a chave de depuração. Para gerar um pacote, configure uma chave de assinatura fora do repositório e defina `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` e `ANDROID_KEY_PASSWORD` no ambiente seguro da máquina de build. Não grave o keystore nem as senhas no Git. O Gradle bloqueia tarefas de release se faltar alguma credencial, se o arquivo do keystore não existir ou se `API_BASE_URL` no ambiente não for uma URL HTTPS. O app também rejeita uma API não HTTPS quando executado em modo release. Nunca use a base SQLite de testes como API publicada.

Depois de fornecer os valores no ambiente seguro e confirmar o hostname de produção, defina também `API_BASE_URL` no ambiente de build. No PowerShell, use `$env:API_BASE_URL='https://api.exemplo'` e execute `flutter build appbundle --release --dart-define=API_BASE_URL=$env:API_BASE_URL`. Substitua `https://api.exemplo` pelo endereço confirmado; ele é apenas ilustrativo. Nenhuma chave ou URL de produção está configurada neste projeto. Ainda é necessário testar o pacote num dispositivo Android físico ligado à API autorizada.

## Verificação de integração

Com uma API de desenvolvimento acessível pelo emulador e um usuário e imóvel de teste criados nela, o teste abaixo percorre o formulário de login e confirma que o imóvel aparece:

```powershell
flutter test integration_test/mobile_api_test.dart -d emulator-5554 `
  --dart-define=SMOKE_TEST_EMAIL=seu-usuario-de-teste `
  --dart-define=SMOKE_TEST_PASSWORD=sua-senha-de-teste `
  --dart-define=SMOKE_TEST_PROPERTY_TITLE=Imovel-de-teste
```

Use apenas uma conta e uma base de desenvolvimento para essa verificação. Para outro dispositivo ou endereço de API, acrescente `--dart-define=API_BASE_URL=http://ENDERECO:8000`.
