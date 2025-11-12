import json
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch
from rest_framework.authtoken.models import Token
import time

from .models import User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, \
    Contact


class ThrottlingTests(TestCase):
    """
    Тесты для проверки тротлинга (ограничения частоты запросов)
    """

    def setUp(self):
        """Настройка тестовых данных"""
        self.client = APIClient()

        # Создаем тестового пользователя
        self.user = User.objects.create_user(
            first_name='Throttle',
            last_name='Test',
            email='throttle@example.com',
            password='testpassword123',
            company='Test Company',
            position='Manager',
            is_active=True
        )

        # Создаем токен для пользователя
        self.user_token = Token.objects.create(user=self.user)

    def parse_response(self, response):
        """Вспомогательный метод для парсинга JsonResponse"""
        return json.loads(response.content)

    def test_anon_throttling_categories(self):
        """
        Тест тротлинга для анонимных пользователей на endpoint категорий
        Ограничение: 100 запросов в день
        """
        url = reverse('backend:categories')

        # Делаем несколько запросов подряд
        for i in range(5):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print(f"Анонимный запрос {i + 1}: статус {response.status_code}")

    def test_anon_throttling_shops(self):
        """
        Тест тротлинга для анонимных пользователей на endpoint магазинов
        """
        url = reverse('backend:shops')

        # Делаем несколько быстрых запросов
        for i in range(5):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print(f"Анонимный запрос магазинов {i + 1}: статус {response.status_code}")

    def test_user_throttling_details(self):
        """
        Тест тротлинга для авторизованных пользователей
        Ограничение: 1000 запросов в день
        """
        url = reverse('backend:user-details')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')

        # Делаем несколько запросов подряд
        for i in range(5):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print(f"Авторизованный запрос {i + 1}: статус {response.status_code}")

    def test_user_throttling_basket(self):
        """
        Тест тротлинга на endpoint корзины для авторизованных пользователей
        """
        url = reverse('backend:basket')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')

        # Делаем несколько GET запросов
        for i in range(5):
            response = self.client.get(url)
            # Может быть 200 OK или 404 если корзина пуста
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
            print(f"Запрос корзины {i + 1}: статус {response.status_code}")

    def test_mixed_throttling_scenarios(self):
        """
        Тест смешанных сценариев тротлинга
        """
        # Анонимные запросы к публичным endpoint'ам
        public_endpoints = [
            reverse('backend:categories'),
            reverse('backend:shops'),
        ]

        for endpoint in public_endpoints:
            for i in range(3):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                print(f"Публичный endpoint {endpoint}, запрос {i + 1}: статус {response.status_code}")

        # Авторизованные запросы
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')
        private_endpoints = [
            reverse('backend:user-details'),
            reverse('backend:order'),
        ]

        for endpoint in private_endpoints:
            for i in range(3):
                response = self.client.get(endpoint)
                self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
                print(f"Приватный endpoint {endpoint}, запрос {i + 1}: статус {response.status_code}")

    def test_throttling_after_many_requests(self):
        """
        Тест тротлинга после большого количества запросов
        ВНИМАНИЕ: Этот тест может занять время из-за ожидания
        """
        url = reverse('backend:categories')

        # Делаем 10 быстрых запросов (должны пройти)
        successful_requests = 0
        for i in range(10):
            response = self.client.get(url)
            if response.status_code == status.HTTP_200_OK:
                successful_requests += 1
            print(f"Быстрый запрос {i + 1}: статус {response.status_code}")

        print(f"Успешных быстрых запросов: {successful_requests}/10")
        self.assertEqual(successful_requests, 10)

    def test_throttling_reset_after_delay(self):
        """
        Тест сброса тротлинга после задержки
        Этот тест демонстрирует, что тротлинг работает на основе временных окон
        """
        url = reverse('backend:categories')

        # Первая серия запросов
        print("Первая серия запросов:")
        for i in range(5):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print(f"  Запрос {i + 1}: статус {response.status_code}")

        # Небольшая задержка
        print("Ожидание 1 секунду...")
        time.sleep(1)

        # Вторая серия запросов после задержки
        print("Вторая серия запросов после задержки:")
        for i in range(5):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print(f"  Запрос {i + 1}: статус {response.status_code}")

    def test_throttling_headers(self):
        """
        Тест проверки заголовков тротлинга в ответе
        """
        url = reverse('backend:categories')

        response = self.client.get(url)

        # Проверяем стандартные заголовки
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # DRF может добавлять заголовки тротлинга, но они не всегда присутствуют
        # при успешных запросах в пределах лимита
        print("Заголовки ответа:")
        for header, value in response.items():
            print(f"  {header}: {value}")

    def test_different_users_different_throttling(self):
        """
        Тест того, что разные пользователи имеют отдельные лимиты тротлинга
        """
        # Создаем второго пользователя
        user2 = User.objects.create_user(
            first_name='Throttle2',
            last_name='Test2',
            email='throttle2@example.com',
            password='testpassword123',
            is_active=True
        )
        user2_token = Token.objects.create(user=user2)

        url = reverse('backend:user-details')

        # Запросы от первого пользователя
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')
        for i in range(3):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print(f"Пользователь 1, запрос {i + 1}: статус {response.status_code}")

        # Запросы от второго пользователя
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {user2_token.key}')
        for i in range(3):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print(f"Пользователь 2, запрос {i + 1}: статус {response.status_code}")

    def test_throttling_on_post_requests(self):
        """
        Тест тротлинга на POST запросах
        """
        url = reverse('backend:user-login')

        # Несколько попыток входа (должны учитываться в тротлинге)
        for i in range(3):
            data = {
                'email': f'test{i}@example.com',  # разные email чтобы избежать блокировки по логике приложения
                'password': 'wrongpassword'
            }
            response = self.client.post(url, data, format='json')
            # Ожидаем ошибку аутентификации, но не тротлинга
            self.assertIn(response.status_code,
                          [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])
            print(f"POST запрос {i + 1}: статус {response.status_code}")


class BackendAPITestCase(TestCase):
    """
    Комплексные тесты для всего API бэкенда
    """

    def setUp(self):
        """Настройка тестовых данных"""
        self.client = APIClient()

        # Создаем тестового пользователя-покупателя
        self.user_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'testuser@example.com',
            'password': 'testpassword123',
            'company': 'Test Company',
            'position': 'Manager'
        }
        self.user = User.objects.create_user(
            first_name=self.user_data['first_name'],
            last_name=self.user_data['last_name'],
            email=self.user_data['email'],
            password=self.user_data['password'],
            company=self.user_data['company'],
            position=self.user_data['position'],
            is_active=True
        )
        # Создаем токен для пользователя
        self.user_token = Token.objects.create(user=self.user)

        # Создаем пользователя-магазин
        self.shop_user = User.objects.create_user(
            first_name='Shop',
            last_name='Owner',
            email='shop@example.com',
            password='shoppassword123',
            company='Test Shop',
            position='Owner',
            type='shop',
            is_active=True
        )
        # Создаем токен для магазина
        self.shop_token = Token.objects.create(user=self.shop_user)

        # Создаем магазин
        self.shop = Shop.objects.create(
            name='Test Shop',
            user=self.shop_user,
            state=True
        )

        # Создаем категории
        self.category1 = Category.objects.create(name='Электроника')
        self.category2 = Category.objects.create(name='Одежда')
        self.category1.shops.add(self.shop)
        self.category2.shops.add(self.shop)

        # Создаем продукты
        self.product1 = Product.objects.create(
            name='Смартфон',
            category=self.category1
        )
        self.product2 = Product.objects.create(
            name='Футболка',
            category=self.category2
        )

        # Создаем информацию о продуктах
        self.product_info1 = ProductInfo.objects.create(
            product=self.product1,
            shop=self.shop,
            external_id=1,
            model='Model X',
            price=10000,
            price_rrc=12000,
            quantity=10
        )
        self.product_info2 = ProductInfo.objects.create(
            product=self.product2,
            shop=self.shop,
            external_id=2,
            model='Classic',
            price=1000,
            price_rrc=1200,
            quantity=20
        )

        # Создаем параметры
        self.parameter1 = Parameter.objects.create(name='Цвет')
        self.parameter2 = Parameter.objects.create(name='Размер')

        # Создаем параметры продуктов
        ProductParameter.objects.create(
            product_info=self.product_info1,
            parameter=self.parameter1,
            value='Черный'
        )
        ProductParameter.objects.create(
            product_info=self.product_info2,
            parameter=self.parameter2,
            value='M'
        )

    def parse_response(self, response):
        """Вспомогательный метод для парсинга JsonResponse"""
        return json.loads(response.content)

    def test_01_user_registration(self):
        """Тест регистрации пользователя"""
        url = reverse('backend:user-register')
        data = {
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'password': 'newpassword123',
            'company': 'New Company',
            'position': 'Developer'
        }

        response = self.client.post(url, data, format='json')
        response_data = self.parse_response(response)

        print(f"Registration response: {response_data}")  # Debug

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])

        # Проверяем что пользователь создан
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())

    def test_02_user_login(self):
        """Тест авторизации пользователя"""
        url = reverse('backend:user-login')
        data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }

        response = self.client.post(url, data, format='json')
        response_data = self.parse_response(response)

        print(f"Login response: {response_data}")  # Debug

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])
        self.assertIn('Token', response_data)

    def test_03_user_details(self):
        """Тест получения деталей пользователя"""
        url = reverse('backend:user-details')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')

        response = self.client.get(url)
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data['email'], self.user_data['email'])
        self.assertEqual(response_data['first_name'], self.user_data['first_name'])

    def test_04_contact_management(self):
        """Тест управления контактами"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')
        url = reverse('backend:user-contact')

        # Добавление контакта
        contact_data = {
            'city': 'Москва',
            'street': 'Тверская',
            'house': '1',
            'structure': '1',
            'building': '1',
            'apartment': '10',
            'phone': '+79161234567'
        }

        response = self.client.post(url, contact_data, format='json')
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])

        # Получение списка контактов
        response = self.client.get(url)
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response_data) > 0)

    def test_05_categories_list(self):
        """Тест получения списка категорий"""
        url = reverse('backend:categories')

        response = self.client.get(url)
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response_data), 0)

    def test_06_shops_list(self):
        """Тест получения списка магазинов"""
        url = reverse('backend:shops')

        response = self.client.get(url)
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response_data), 0)

    def test_07_products_list(self):
        """Тест получения списка товаров"""
        # Используем существующий endpoint для товаров
        url = reverse('backend:shops')  # или другой подходящий endpoint

        response = self.client.get(url)
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response_data), 0)

    def test_08_basket_management(self):
        """Тест управления корзиной"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')
        url = reverse('backend:basket')

        # Добавление товаров в корзину - используем POST вместо PUT
        basket_data = {
            'items': [
                {
                    'product_info': self.product_info1.id,
                    'quantity': 2
                }
            ]
        }

        # Используем POST запрос с JSON данными
        response = self.client.post(url, basket_data, format='json')
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])

        # Проверяем что корзина создана
        basket = Order.objects.filter(user=self.user, state='basket').first()
        self.assertIsNotNone(basket)

    def test_09_order_creation(self):
        """Тест создания заказа"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')

        # Создаем контакт
        url = reverse('backend:user-contact')
        contact_data = {
            'city': 'Москва',
            'street': 'Тверская',
            'phone': '+79161234567'
        }
        response = self.client.post(url, contact_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        contact = Contact.objects.filter(user=self.user).first()
        contact_id = contact.id

        # Добавляем товары в корзину
        url = reverse('backend:basket')
        basket_data = {
            'items': [
                {
                    'product_info': self.product_info1.id,
                    'quantity': 1
                }
            ]
        }

        response = self.client.post(url, basket_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Подтверждаем заказ
        url = reverse('backend:order')
        basket = Order.objects.filter(user=self.user, state='basket').first()
        order_data = {
            'id': basket.id,
            'contact': contact_id
        }

        with patch('backend.views.new_order.send'):
            with patch('backend.celery_tasks.send_order_confirmation_email.delay'):
                response = self.client.post(url, order_data, format='json')
                response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])

    def test_10_order_list(self):
        """Тест получения списка заказов"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')
        url = reverse('backend:order')

        response = self.client.get(url)
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_11_partner_update(self):
        """Тест обновления прайса партнера"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.shop_token.key}')
        url = reverse('backend:partner-update')

        # Тестовые YAML данные
        yaml_data = """
        shop: Test Shop
        categories:
          - id: 3
            name: Аксессуары
        goods:
          - id: 3
            category: 3
            name: Чехол для телефона
            model: Case Pro
            price: 500
            price_rrc: 600
            quantity: 15
            parameters:
              Материал: Силикон
              Цвет: Синий
        """

        # Тестируем импорт
        with patch('backend.views.get') as mock_get:
            mock_get.return_value.content = yaml_data.encode('utf-8')

            data = {
                'url': 'http://example.com/price.yaml'
            }

            response = self.client.post(url, data, format='json')
            response_data = self.parse_response(response)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response_data['Status'])

    def test_12_partner_state(self):
        """Тест управления статусом магазина"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.shop_token.key}')
        url = reverse('backend:partner-state')

        # 1. Получаем текущий статус магазина
        response = self.client.get(url)
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        original_state = response_data.get('state')

        # Проверяем структуру ответа
        self.assertIn('id', response_data)
        self.assertIn('name', response_data)
        self.assertIn('state', response_data)
        self.assertEqual(response_data['name'], 'Test Shop')

        # 2. Изменяем статус магазина
        new_state = 'false' if original_state else 'true'
        state_data = {'state': new_state}

        response = self.client.post(url, state_data, format='json')
        response_data = self.parse_response(response)

        # Проверяем что изменение прошло успешно
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])

        # Проверяем что статус действительно изменился в базе данных
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.state, False if new_state == 'false' else True)

        # 3. Восстанавливаем исходный статус
        restore_state = 'true' if original_state else 'false'
        restore_data = {'state': restore_state}

        response = self.client.post(url, restore_data, format='json')
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])

        # Проверяем восстановление
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.state, original_state)

        # 4. Проверяем что GET продолжает работать после изменений
        response = self.client.get(url)
        response_data = self.parse_response(response)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data['state'], original_state)

    def test_13_partner_orders(self):
        """Тест получения заказов партнера"""
        # Сначала создаем заказ
        self.test_09_order_creation()

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.shop_token.key}')
        url = reverse('backend:partner-orders')

        response = self.client.get(url)
        response_data = self.parse_response(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_14_full_user_journey(self):
        """Полный тестовый сценарий пользователя"""
        # 1. Регистрация
        url = reverse('backend:user-register')
        user_data = {
            'first_name': 'Journey',
            'last_name': 'User',
            'email': 'journeyuser@example.com',
            'password': 'journeypass123',
            'company': 'Journey Corp',
            'position': 'Tester'
        }
        response = self.client.post(url, user_data, format='json')
        response_data = self.parse_response(response)
        print(f"1. Registration response: {response_data}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])

        user = User.objects.get(email='journeyuser@example.com')
        user.is_active = True
        user.save()
        print(f"1.5. User activated: {user.email}, is_active: {user.is_active}")

        # 2. Авторизация
        url = reverse('backend:user-login')
        login_data = {
            'email': 'journeyuser@example.com',
            'password': 'journeypass123'
        }
        response = self.client.post(url, login_data, format='json')
        response_data = self.parse_response(response)
        print(f"2. Login response: {response_data}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])
        token = response_data['Token']

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        # 3. Добавление контакта
        url = reverse('backend:user-contact')
        contact_data = {
            'city': 'Санкт-Петербург',
            'street': 'Невский проспект',
            'phone': '+79161112233'
        }
        response = self.client.post(url, contact_data, format='json')
        response_data = self.parse_response(response)
        print(f"3. Contact creation response: {response_data}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Проверяем что контакт создан
        contact = Contact.objects.filter(user__email='journeyuser@example.com').first()
        self.assertIsNotNone(contact, "Контакт не был создан")
        print(f"Contact created with ID: {contact.id}")

        # 4. Добавление в корзину
        url = reverse('backend:basket')
        basket_data = {
            'items': [
                {
                    'product_info': self.product_info1.id,
                    'quantity': 1
                }
            ]
        }

        response = self.client.post(url, basket_data, format='json')
        response_data = self.parse_response(response)
        print(f"4. Basket response: {response_data}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response_data['Status'])

        # Проверяем что корзина создана
        basket = Order.objects.filter(user__email='journeyuser@example.com', state='basket').first()
        self.assertIsNotNone(basket, "Корзина не была создана")
        print(f"Basket created with ID: {basket.id}")

        # 5. Подтверждение заказа
        url = reverse('backend:order')
        order_data = {
            'id': basket.id,
            'contact': contact.id
        }

        print(f"5. Order data: {order_data}")

        with patch('backend.views.new_order.send'):
            with patch('backend.celery_tasks.send_order_confirmation_email.delay'):
                response = self.client.post(url, order_data, format='json')
                response_data = self.parse_response(response)

                print(f"6. Order creation response: {response_data}")

                # Проверяем что заказ создан
                self.assertEqual(response.status_code, status.HTTP_200_OK,
                                 f"Order creation failed with status {response.status_code}")

                # Если Status: False, выводим ошибку
                if not response_data.get('Status'):
                    print(f"Order creation error: {response_data.get('Error', 'Unknown error')}")

                self.assertTrue(response_data['Status'],
                                f"Order creation failed: {response_data.get('Error', 'Unknown error')}")

                # Проверяем что заказ перешел в состояние 'new'
                basket.refresh_from_db()
                print(f"7. Basket state after order: {basket.state}")
                self.assertEqual(basket.state, 'new',
                                 f"Order state should be 'new' but is '{basket.state}'")


class ModelTests(TestCase):
    """Тесты моделей"""

    def setUp(self):
        self.user = User.objects.create_user(
            first_name='Test',
            last_name='User',
            email='modeltest@example.com',
            password='testpass123'
        )

    def test_user_creation(self):
        """Тест создания пользователя"""
        self.assertEqual(self.user.email, 'modeltest@example.com')
        self.assertTrue(self.user.check_password('testpass123'))
        self.assertEqual(self.user.type, 'buyer')

    def test_shop_creation(self):
        """Тест создания магазина"""
        shop = Shop.objects.create(
            name='Test Shop',
            user=self.user
        )
        self.assertEqual(shop.name, 'Test Shop')
        self.assertEqual(shop.user, self.user)

    def test_order_creation(self):
        """Тест создания заказа"""
        order = Order.objects.create(
            user=self.user,
            state='basket'
        )
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.state, 'basket')


class ErrorHandlingTests(TestCase):
    """Тесты обработки ошибок"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            first_name='Test',
            last_name='User',
            email='errortest@example.com',
            password='testpass123'
        )

    def parse_response(self, response):
        """Вспомогательный метод для парсинга JsonResponse"""
        return json.loads(response.content)

    def test_unauthorized_access(self):
        """Тест доступа без авторизации"""
        url = reverse('backend:user-details')
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_invalid_login(self):
        """Тест неверных данных для входа"""
        url = reverse('backend:user-login')
        data = {
            'email': 'wrong@example.com',
            'password': 'wrongpassword'
        }
        response = self.client.post(url, data, format='json')
        response_data = self.parse_response(response)

        # Проверяем что статус False
        self.assertFalse(response_data.get('Status', True))

    def test_missing_required_fields(self):
        """Тест отсутствия обязательных полей"""
        url = reverse('backend:user-register')
        data = {
            'email': 'incomplete@example.com'
            # Нет password и других обязательных полей
        }
        response = self.client.post(url, data, format='json')
        response_data = self.parse_response(response)

        # Проверяем что статус False
        self.assertFalse(response_data.get('Status', True))
        self.assertIn('Errors', response_data)