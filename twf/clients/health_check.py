import requests
import socket

TWF_EXTERNAL_SERVICES = {
    "OpenAI": "https://api.openai.com/v1/models",
    "Anthropic": "https://api.anthropic.com/v1/models",
    "Google AI": "https://generativelanguage.googleapis.com/v1/models",
    "Mistral": "https://api.mistral.ai/v1/models",
    "Deepseek": "https://api.deepseek.com/v1",
    "Qwen": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
    "Transkribus": "https://transkribus.eu/TrpServer/rest",
    "Wikidata": "https://www.wikidata.org/w/api.php",
    "GND": "https://services.dnb.de/sru/authorities",
    "Geonames": "http://api.geonames.org",
    "Zenodo": "https://zenodo.org/api/deposit/depositions",
}


def check_service_status():
    """
    Check the availability status of all TWF external services.

    Performs DNS resolution and HTTP requests to verify each service is reachable.
    Handles authentication errors (401, 403) as successful since they indicate the service is up.

    Returns:
        dict: Dictionary mapping service names to status dictionaries with keys:
            - status: Human-readable status string with emoji indicator
            - error: Error message if service is unreachable, empty string otherwise
    """
    results = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }

    for service, url in TWF_EXTERNAL_SERVICES.items():
        try:
            # Extract domain for low-level reachability check
            domain = url.split("//")[1].split("/")[0]
            socket.gethostbyname(domain)  # DNS resolution test

            # Send request mimicking a browser
            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code in [200, 401, 403]:  # Ignore auth issues
                results[service] = {"status": "✅ accessible", "error": ""}
            else:
                results[service] = {
                    "status": "⚠️ Unexpected Response",
                    "error": f"HTTP {response.status_code}",
                }

        except requests.ConnectionError:
            results[service] = {
                "status": "❌ Connection Error",
                "error": "Cannot reach the server.",
            }
        except requests.Timeout:
            results[service] = {
                "status": "❌ Timeout",
                "error": "The request timed out.",
            }
        except socket.gaierror:
            results[service] = {
                "status": "❌ DNS Error",
                "error": "Could not resolve hostname.",
            }
        except Exception as e:
            results[service] = {"status": "❌ Error", "error": str(e)}

    return results
