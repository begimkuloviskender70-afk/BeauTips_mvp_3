#!/usr/bin/env python3
"""
Скрипт для тестирования API после деплоя на Railway
"""
import requests
import sys
import json
from typing import Dict, Any

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def test_endpoint(url: str, method: str = 'GET', data: Dict = None, headers: Dict = None) -> bool:
    """Тестирование endpoint"""
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=10)
        else:
            response = requests.post(url, json=data, headers=headers, timeout=10)
        
        if response.status_code < 400:
            print(f"  {Colors.GREEN}✓{Colors.END} {method} {url}")
            print(f"    Status: {response.status_code}")
            return True
        else:
            print(f"  {Colors.RED}✗{Colors.END} {method} {url}")
            print(f"    Status: {response.status_code}")
            print(f"    Error: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"  {Colors.RED}✗{Colors.END} {method} {url}")
        print(f"    Error: {str(e)}")
        return False

def main():
    if len(sys.argv) < 2:
        print(f"{Colors.RED}Usage: python test_api.py <your-railway-url>{Colors.END}")
        print(f"Example: python test_api.py https://your-app.railway.app")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    
    print("=" * 60)
    print(f"{Colors.BLUE}🧪 Тестирование API на Railway{Colors.END}")
    print(f"URL: {base_url}")
    print("=" * 60)
    print()
    
    results = []
    
    # Test 1: Health Check
    print(f"{Colors.YELLOW}1. Health Check{Colors.END}")
    results.append(test_endpoint(f"{base_url}/"))
    print()
    
    # Test 2: API Documentation
    print(f"{Colors.YELLOW}2. API Documentation{Colors.END}")
    results.append(test_endpoint(f"{base_url}/api/docs"))
    print()
    
    # Test 3: Schema Test
    print(f"{Colors.YELLOW}3. Schema Test{Colors.END}")
    results.append(test_endpoint(f"{base_url}/api/test/schema"))
    print()
    
    # Test 4: Register (должен вернуть ошибку без данных, но endpoint работает)
    print(f"{Colors.YELLOW}4. Register Endpoint (no data){Colors.END}")
    response = requests.post(f"{base_url}/api/auth/register", timeout=10)
    if response.status_code == 422:  # Validation error - это OK
        print(f"  {Colors.GREEN}✓{Colors.END} POST {base_url}/api/auth/register")
        print(f"    Status: {response.status_code} (validation error - endpoint works)")
        results.append(True)
    else:
        print(f"  {Colors.RED}✗{Colors.END} POST {base_url}/api/auth/register")
        print(f"    Unexpected status: {response.status_code}")
        results.append(False)
    print()
    
    # Test 5: Login (должен вернуть ошибку без данных, но endpoint работает)
    print(f"{Colors.YELLOW}5. Login Endpoint (no data){Colors.END}")
    response = requests.post(f"{base_url}/api/auth/login", timeout=10)
    if response.status_code == 422:  # Validation error - это OK
        print(f"  {Colors.GREEN}✓{Colors.END} POST {base_url}/api/auth/login")
        print(f"    Status: {response.status_code} (validation error - endpoint works)")
        results.append(True)
    else:
        print(f"  {Colors.RED}✗{Colors.END} POST {base_url}/api/auth/login")
        print(f"    Unexpected status: {response.status_code}")
        results.append(False)
    print()
    
    # Summary
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"{Colors.GREEN}✅ Все тесты пройдены! ({passed}/{total}){Colors.END}")
        print(f"{Colors.GREEN}🚀 API работает корректно на Railway{Colors.END}")
        return 0
    else:
        print(f"{Colors.YELLOW}⚠️  Пройдено тестов: {passed}/{total}{Colors.END}")
        if passed >= total * 0.6:
            print(f"{Colors.YELLOW}API частично работает - проверьте логи Railway{Colors.END}")
            return 0
        else:
            print(f"{Colors.RED}❌ Большинство тестов не прошли{Colors.END}")
            print(f"{Colors.RED}Проверьте конфигурацию и логи Railway{Colors.END}")
            return 1
    print("=" * 60)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Тестирование прервано{Colors.END}")
        sys.exit(1)
