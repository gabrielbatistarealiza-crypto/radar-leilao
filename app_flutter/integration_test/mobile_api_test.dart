import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:radar_leilao/src/api_client.dart';
import 'package:radar_leilao/src/radar_app.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('faz login e carrega imóveis pela API', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    const email = String.fromEnvironment('SMOKE_TEST_EMAIL');
    const password = String.fromEnvironment('SMOKE_TEST_PASSWORD');
    const propertyTitle = String.fromEnvironment('SMOKE_TEST_PROPERTY_TITLE');
    expect(email, isNotEmpty,
        reason: 'Defina SMOKE_TEST_EMAIL para a conta de teste.');
    expect(password, isNotEmpty,
        reason: 'Defina SMOKE_TEST_PASSWORD para a conta de teste.');
    expect(propertyTitle, isNotEmpty,
        reason: 'Defina SMOKE_TEST_PROPERTY_TITLE para o imóvel esperado.');

    final preferences = await SharedPreferences.getInstance();
    final api = ApiClient();
    addTearDown(api.close);
    final testToken = await api.login(email, password);
    final testUser = await api.getCurrentUser(testToken);
    final favoritesKey = 'favorite_property_ids_${testUser['id']}';
    await preferences.remove(favoritesKey);

    await tester.pumpWidget(const RadarApp());
    await tester.enterText(find.byType(TextField).at(0), email);
    await tester.enterText(find.byType(TextField).at(1), password);
    await tester.tap(find.widgetWithText(FilledButton, 'Entrar'));

    final deadline = DateTime.now().add(const Duration(seconds: 30));
    while (DateTime.now().isBefore(deadline) &&
        find.text(propertyTitle).evaluate().isEmpty) {
      await tester.pump(const Duration(milliseconds: 250));
    }

    expect(find.text('Oportunidades'), findsOneWidget);
    expect(find.text(propertyTitle), findsOneWidget);

    // Exercise alert CRUD and notification ownership through the real API.
    // The fixture provisions only synthetic users and a disposable SQLite DB.
    final firstToken = await api.login(email, password);
    final secondToken = await api.login(
      const String.fromEnvironment('SMOKE_TEST_OTHER_EMAIL',
          defaultValue: 'mobile.other@example.com'),
      const String.fromEnvironment('SMOKE_TEST_OTHER_PASSWORD',
          defaultValue: 'MobileOther-2026!'),
    );
    final secondUser = await api.getCurrentUser(secondToken);
    final otherFavoritesKey = 'favorite_property_ids_${secondUser['id']}';
    await preferences.remove(otherFavoritesKey);
    expect(otherFavoritesKey, isNot(favoritesKey));
    expect(preferences.getStringList(otherFavoritesKey), isNull,
        reason: 'A conta B não pode herdar favoritos locais da conta A.');
    final property = (await api.getProperties(firstToken))
        .firstWhere((item) => item['titulo'] == propertyTitle);
    final propertyId = property['id'] as int;
    final currentUser = await api.getCurrentUser(firstToken);
    final opportunities =
        await api.getPropertyOpportunities(firstToken, propertyId);
    final opportunity = opportunities.isNotEmpty
        ? opportunities.first
        : await api.createPropertyOpportunity(
            firstToken, propertyId, currentUser['id'] as int);
    final opportunityId = opportunity['id'] as int;
    final completeScenario =
        await api.saveProfitabilityScenario(firstToken, opportunityId, {
      'nome': 'Cenário mobile completo',
      'preco_aquisicao': 120000,
      'impostos_taxas': 10000,
      'custos_juridicos': 5000,
      'reformas': 25000,
      'outras_despesas': 5000,
      'valor_revenda': 300000,
      'observacoes': 'Premissa sintética de integração',
    });
    double amount(String key) => double.parse('${completeScenario[key]}');
    expect(amount('custo_total'), 165000);
    expect(amount('lucro_estimado'), 135000);
    expect(amount('margem_revenda'), 45);
    expect(amount('roi'), closeTo(81.8181818, .0001));
    expect(completeScenario['custos_nao_informados'], isEmpty);
    final incompleteScenario =
        await api.saveProfitabilityScenario(firstToken, opportunityId, {
      'nome': 'Cenário mobile incompleto',
      'preco_aquisicao': 120000,
      'valor_revenda': 200000,
    });
    expect(incompleteScenario['custos_nao_informados'], [
      'Impostos e taxas',
      'Custos jurídicos',
      'Reformas',
      'Outras despesas',
    ]);
    final storedScenarios =
        await api.getProfitabilityScenarios(firstToken, opportunityId);
    expect(storedScenarios.any((item) => item['id'] == completeScenario['id']),
        isTrue);
    expect(
        storedScenarios.any((item) => item['id'] == incompleteScenario['id']),
        isTrue);
    await expectLater(api.getProfitabilityScenarios(secondToken, opportunityId),
        throwsA(isA<ApiException>()));
    final createdAlert = await api.saveAlert(firstToken, {
      'nome': 'Filtro de integração mobile',
      'estado': 'SP',
      'cidade': 'Lisboa',
      'preco_maximo': 150000,
      'desconto_minimo': 30,
      'roi_minimo': null,
      'simulacao_id': null,
      'alertar_prazos_dias': 14,
    });
    final alertId = createdAlert['id'] as int;
    expect(
        (await api.getAlerts(firstToken)).any((item) => item['id'] == alertId),
        isTrue);
    expect(
        (await api.getAlerts(secondToken)).any((item) => item['id'] == alertId),
        isFalse);
    await api.saveAlert(
        firstToken,
        {
          'nome': 'Filtro mobile atualizado',
          'estado': 'SP',
          'cidade': 'Lisboa',
          'preco_maximo': 140000,
          'desconto_minimo': 35,
          'roi_minimo': null,
          'simulacao_id': null,
          'alertar_prazos_dias': 10,
        },
        id: alertId);
    expect(
        (await api.getAlerts(firstToken))
            .firstWhere((item) => item['id'] == alertId)['nome'],
        'Filtro mobile atualizado');

    await tester.tap(find.byKey(const ValueKey('alerts-open')));
    await tester.pumpAndSettle();
    expect(find.text('Alertas e notificações'), findsOneWidget);
    expect(find.text('Filtro mobile atualizado'), findsWidgets);
    expect(find.text('Notificação sintética de teste'), findsOneWidget);
    final markAsRead = find.byTooltip('Marcar como lida');
    if (markAsRead.evaluate().isNotEmpty) {
      await tester.tap(markAsRead.first);
      await tester.pumpAndSettle();
    }

    final firstNotifications = await api.getNotifications(firstToken);
    final ownNotification = firstNotifications.firstWhere(
        (item) => '${item['evento']}'.startsWith('mobile-smoke:own'));
    expect(ownNotification['lida'], isTrue);
    expect(
        (await api.getNotifications(secondToken))
            .any((item) => '${item['evento']}'.startsWith('mobile-smoke:own')),
        isFalse);
    expect(
        (await api.getNotifications(secondToken)).firstWhere((item) =>
            '${item['evento']}'.startsWith('mobile-smoke:other'))['lida'],
        isFalse);
    await api.deleteAlert(firstToken, alertId);
    expect(
        (await api.getAlerts(firstToken)).any((item) => item['id'] == alertId),
        isFalse);
    await tester.pageBack();
    await tester.pumpAndSettle();

    final search = find.byType(TextField).first;
    await tester.enterText(search, 'Lisboa');
    await tester.pumpAndSettle();
    expect(find.text(propertyTitle), findsOneWidget);
    await tester.enterText(search, 'termo sem resultados');
    await tester.pumpAndSettle();
    expect(find.text('Nada por aqui'), findsOneWidget);
    await tester.enterText(search, '');
    await tester.pumpAndSettle();

    await tester.tap(find.text('Mais filtros'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Cidade'), 'Lisboa');
    await tester.enterText(find.widgetWithText(TextField, 'Estado (UF)'), 'SP');
    await tester.enterText(
        find.widgetWithText(TextField, 'Preço máximo'), '120000');
    await tester.enterText(
        find.widgetWithText(TextField, 'Desconto mínimo'), '40');
    await tester.tap(find.text('Aplicar filtros'));
    await tester.pumpAndSettle();
    expect(find.text(propertyTitle), findsOneWidget);

    await tester.tap(find.text('Filtros (4)'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Limpar'));
    await tester.tap(find.text('Aplicar filtros'));
    await tester.pumpAndSettle();
    expect(find.text('Mais filtros'), findsOneWidget);

    await tester.tap(find.text('Ativos'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Todos').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Destaques'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Menor preço').last);
    await tester.pumpAndSettle();
    expect(find.text(propertyTitle), findsOneWidget);

    final favoriteButton = find.byTooltip('Adicionar aos favoritos').first;
    await tester.ensureVisible(favoriteButton);
    await tester.tap(favoriteButton);
    await tester.pumpAndSettle();
    expect(preferences.getStringList(favoritesKey), hasLength(1));
    await tester.tap(find.byKey(const ValueKey('favorites-toggle')));
    await tester.pumpAndSettle();
    expect(find.text('Oportunidades'), findsOneWidget);
    expect(find.text(propertyTitle), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('favorites-toggle')));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text(propertyTitle));
    await tester.pumpAndSettle();
    await tester.tap(find.text(propertyTitle));
    await tester.pumpAndSettle();
    expect(find.text('Detalhes do imóvel'), findsOneWidget);
    expect(find.text('Rua de Teste, 123, Lisboa, SP'), findsOneWidget);
    expect(find.text('R\$ 120.000,00'), findsOneWidget);
    expect(find.text('R\$ 200.000,00'), findsOneWidget);
    expect(find.text('40%'), findsOneWidget);
    expect(find.text('Leilão SFI - Edital Único'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('detail-favorite')));
    await tester.pumpAndSettle();
    expect(preferences.getStringList(favoritesKey), isEmpty);
    await tester.tap(find.byKey(const ValueKey('detail-favorite')));
    await tester.pumpAndSettle();
    expect(preferences.getStringList(favoritesKey), hasLength(1));
    expect(find.text('1 / 2'), findsOneWidget);
    await tester.fling(find.byType(PageView), const Offset(-300, 0), 1200);
    await tester.pumpAndSettle();
    expect(find.text('2 / 2'), findsOneWidget);
    final simulatorButton = find.byKey(const ValueKey('profitability-open'));
    await tester.drag(find.byType(ListView).last, const Offset(0, -1000));
    await tester.pumpAndSettle();
    await tester.tap(simulatorButton);
    await tester.pumpAndSettle();
    expect(find.text('Simulador de rentabilidade'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();

    // Remount the app to model a fresh launch and verify the saved favorite.
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await tester.pumpWidget(const RadarApp());
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), email);
    await tester.enterText(find.byType(TextField).at(1), password);
    await tester.tap(find.widgetWithText(FilledButton, 'Entrar'));
    final relaunchDeadline = DateTime.now().add(const Duration(seconds: 30));
    while (DateTime.now().isBefore(relaunchDeadline) &&
        find.text(propertyTitle).evaluate().isEmpty) {
      await tester.pump(const Duration(milliseconds: 250));
    }
    expect(find.text(propertyTitle), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('favorites-toggle')));
    await tester.pumpAndSettle();
    expect(find.text('Oportunidades'), findsOneWidget);
    expect(find.text(propertyTitle), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('logout')));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(FilledButton, 'Entrar'), findsOneWidget);
    await tester.enterText(
        find.byType(TextField).at(0),
        const String.fromEnvironment('SMOKE_TEST_OTHER_EMAIL',
            defaultValue: 'mobile.other@example.com'));
    await tester.enterText(
        find.byType(TextField).at(1),
        const String.fromEnvironment('SMOKE_TEST_OTHER_PASSWORD',
            defaultValue: 'MobileOther-2026!'));
    await tester.tap(find.widgetWithText(FilledButton, 'Entrar'));
    final accountSwitchDeadline =
        DateTime.now().add(const Duration(seconds: 30));
    while (DateTime.now().isBefore(accountSwitchDeadline) &&
        find.text(propertyTitle).evaluate().isEmpty) {
      await tester.pump(const Duration(milliseconds: 250));
    }
    await tester.tap(find.byKey(const ValueKey('favorites-toggle')));
    await tester.pumpAndSettle();
    expect(find.text('Oportunidades'), findsOneWidget);
    expect(find.text(propertyTitle), findsNothing,
        reason: 'A conta B não deve ver favoritos locais da conta A.');
    expect(preferences.getStringList(favoritesKey), hasLength(1),
        reason: 'A troca de conta deve preservar os favoritos da conta A.');
  });
}
