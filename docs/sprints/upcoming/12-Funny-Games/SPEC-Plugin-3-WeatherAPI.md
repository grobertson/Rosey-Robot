# Sprint 9 - Plugin 3: Weather API

**Complexity:** ⭐⭐⭐☆☆ (Medium)  
**Effort:** 5 hours  
**Priority:** External I/O & Services  
**Status:** Specification Complete

## Overview

The Weather API plugin provides current weather and forecast information by integrating with OpenWeatherMap API. This plugin demonstrates external HTTP calls, service provider pattern, caching, and graceful error handling.

### Purpose

- **User Value:** Quick weather checks in chat
- **Architecture Value:** Validates external I/O, service provider, caching
- **Learning Value:** Demonstrates HTTP client, async patterns, service registry

### Features

- Current weather by location
- 3-day forecast
- Temperature in Celsius and Fahrenheit
- Weather conditions (clear, cloudy, rain, etc.)
- Wind speed and humidity
- Service provider (other plugins can use WeatherService)
- 10-minute caching (configurable)

## Commands

### `!weather <location>`

Get current weather for a location.

**Examples:**

```bash
!weather Seattle
🌤️ Seattle, WA:
  Currently: 15°C (59°F), Partly Cloudy
  Feels like: 13°C (55°F)
  Humidity: 65%
  Wind: 8 km/h NW

!weather London
🌧️ London, UK:
  Currently: 10°C (50°F), Light Rain
  Feels like: 8°C (46°F)
  Humidity: 82%
  Wind: 12 km/h SW
```

### `!forecast <location>`

Get 3-day weather forecast.

**Examples:**

```bash
!forecast Seattle
📅 3-Day Forecast for Seattle, WA:

Wednesday:
  ☀️ Sunny, High: 18°C (64°F), Low: 12°C (54°F)
  
Thursday:
  ⛅ Partly Cloudy, High: 16°C (61°F), Low: 11°C (52°F)
  
Friday:
  🌧️ Rain, High: 14°C (57°F), Low: 10°C (50°F)
```

**Error Handling:**

```bash
!weather InvalidCityXYZ
❌ Location not found: InvalidCityXYZ

!weather
❌ Please provide a location
```

## Configuration

File: `plugins/weather/config.json`

```json
{
  "api_key": "your_openweathermap_api_key_here",
  "cache_duration": 3600,
  "rate_limit": 60,
  "default_units": "metric"
}
```

**Configuration Options:**

- `api_key`: OpenWeatherMap API key (required)
- `cache_duration`: Cache TTL in seconds (default: 3600 = 1 hour, recommend 1-3 hours)
- `rate_limit`: Max API calls per minute (default: 60)
- `default_units`: "metric" or "imperial" (default: "metric")

## Service Provider

The WeatherService can be used by other plugins:

```python
# In another plugin
weather_service = self.get_service('weather')
if weather_service:
    weather_data = await weather_service.get_current_weather('Seattle')
    temp = weather_data['temp']
```

**Service API:**

- `get_current_weather(location: str) -> Dict[str, Any]`
- `get_forecast(location: str, days: int = 3) -> List[Dict[str, Any]]`

## Implementation

### File Structure

```
plugins/weather/
├── __init__.py
├── plugin.py
├── service.py
└── config.json
```

### Code: `plugins/weather/__init__.py`

```python
"""Weather API plugin for cytube-bot."""

from .plugin import WeatherPlugin
from .service import WeatherService

__all__ = ['WeatherPlugin', 'WeatherService']
```

### Code: `plugins/weather/config.json`

```json
{
  "api_key": "your_openweathermap_api_key_here",
  "cache_duration": 3600,
  "rate_limit": 60,
  "default_units": "metric"
}
```

### Code: `plugins/weather/service.py`

```python
"""
Weather Service

Provides weather data fetching with caching and rate limiting.
"""

import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional


class WeatherService:
    """Service for fetching weather data from OpenWeatherMap."""
    
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    
    def __init__(self, api_key: str, cache_duration: int = 600, rate_limit: int = 60):
        """
        Initialize weather service.
        
        Args:
            api_key: OpenWeatherMap API key
            cache_duration: Cache TTL in seconds
            rate_limit: Max API calls per minute
        """
        self.api_key = api_key
        self.cache_duration = cache_duration
        self.rate_limit = rate_limit
        
        # HTTP session (created during start)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Cache: {location: (data, timestamp)}
        self.cache: Dict[str, tuple] = {}
        
        # Rate limiting
        self.call_count = 0
        self.rate_limit_reset = datetime.now() + timedelta(minutes=1)
    
    async def start(self):
        """Start the service (create HTTP session)."""
        self.session = aiohttp.ClientSession()
    
    async def stop(self):
        """Stop the service (close HTTP session)."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_current_weather(self, location: str) -> Optional[Dict[str, Any]]:
        """
        Get current weather for a location.
        
        Args:
            location: City name or "City, Country"
        
        Returns:
            Weather data dict or None if not found
        """
        # Check cache
        cache_key = f"current_{location.lower()}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key][0]
        
        # Check rate limit
        if not await self._check_rate_limit():
            return None
        
        # Fetch from API
        url = f"{self.BASE_URL}/weather"
        params = {
            'q': location,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 404:
                    return None  # Location not found
                
                response.raise_for_status()
                data = await response.json()
                
                # Parse response
                result = {
                    'location': data['name'],
                    'country': data['sys']['country'],
                    'temp': data['main']['temp'],
                    'feels_like': data['main']['feels_like'],
                    'humidity': data['main']['humidity'],
                    'condition': data['weather'][0]['main'],
                    'description': data['weather'][0]['description'],
                    'wind_speed': data['wind']['speed'],
                    'wind_direction': self._degrees_to_direction(data['wind'].get('deg', 0))
                }
                
                # Cache result
                self.cache[cache_key] = (result, datetime.now())
                
                return result
        
        except aiohttp.ClientError as e:
            # Network error
            return None
    
    async def get_forecast(self, location: str, days: int = 3) -> Optional[List[Dict[str, Any]]]:
        """
        Get weather forecast for a location.
        
        Args:
            location: City name or "City, Country"
            days: Number of days (1-5)
        
        Returns:
            List of forecast data dicts or None if not found
        """
        # Check cache
        cache_key = f"forecast_{location.lower()}_{days}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key][0]
        
        # Check rate limit
        if not await self._check_rate_limit():
            return None
        
        # Fetch from API
        url = f"{self.BASE_URL}/forecast"
        params = {
            'q': location,
            'appid': self.api_key,
            'units': 'metric',
            'cnt': days * 8  # API returns 3-hour intervals
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 404:
                    return None
                
                response.raise_for_status()
                data = await response.json()
                
                # Group by day
                daily_forecasts = self._group_by_day(data['list'], days)
                
                # Cache result
                self.cache[cache_key] = (daily_forecasts, datetime.now())
                
                return daily_forecasts
        
        except aiohttp.ClientError:
            return None
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self.cache:
            return False
        
        data, timestamp = self.cache[key]
        age = (datetime.now() - timestamp).total_seconds()
        
        return age < self.cache_duration
    
    async def _check_rate_limit(self) -> bool:
        """Check and enforce rate limiting."""
        now = datetime.now()
        
        # Reset counter if minute elapsed
        if now >= self.rate_limit_reset:
            self.call_count = 0
            self.rate_limit_reset = now + timedelta(minutes=1)
        
        # Check limit
        if self.call_count >= self.rate_limit:
            # Wait until reset
            wait_time = (self.rate_limit_reset - now).total_seconds()
            await asyncio.sleep(wait_time)
            self.call_count = 0
            self.rate_limit_reset = datetime.now() + timedelta(minutes=1)
        
        self.call_count += 1
        return True
    
    def _degrees_to_direction(self, degrees: float) -> str:
        """Convert wind direction degrees to compass direction."""
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(degrees / 45) % 8
        return directions[index]
    
    def _group_by_day(self, forecast_list: List[Dict], days: int) -> List[Dict[str, Any]]:
        """Group 3-hour forecasts into daily summaries."""
        daily = []
        current_day = None
        day_data = []
        
        for item in forecast_list:
            date = datetime.fromtimestamp(item['dt']).date()
            
            if date != current_day:
                if day_data:
                    daily.append(self._summarize_day(day_data))
                current_day = date
                day_data = [item]
            else:
                day_data.append(item)
            
            if len(daily) >= days:
                break
        
        # Add last day
        if day_data and len(daily) < days:
            daily.append(self._summarize_day(day_data))
        
        return daily
    
    def _summarize_day(self, day_data: List[Dict]) -> Dict[str, Any]:
        """Summarize 3-hour forecasts into daily summary."""
        temps = [item['main']['temp'] for item in day_data]
        conditions = [item['weather'][0]['main'] for item in day_data]
        
        # Most common condition
        condition = max(set(conditions), key=conditions.count)
        
        return {
            'date': datetime.fromtimestamp(day_data[0]['dt']),
            'temp_high': max(temps),
            'temp_low': min(temps),
            'condition': condition,
            'description': day_data[0]['weather'][0]['description']
        }
```

### Code: `plugins/weather/plugin.py`

```python
"""
Weather Plugin

Provides weather commands using WeatherService.
"""

from typing import Optional

from lib.plugin import Plugin
from lib.channel import Channel
from lib.user import User
from .service import WeatherService


class WeatherPlugin(Plugin):
    """Plugin for weather information."""
    
    # Weather condition emojis
    CONDITION_EMOJIS = {
        'Clear': '☀️',
        'Clouds': '⛅',
        'Rain': '🌧️',
        'Drizzle': '🌦️',
        'Thunderstorm': '⛈️',
        'Snow': '❄️',
        'Mist': '🌫️',
        'Fog': '🌫️'
    }
    
    def __init__(self, manager):
        """Initialize the weather plugin."""
        super().__init__(manager)
        self.name = "weather"
        self.version = "1.0.0"
        self.description = "Get weather and forecast information"
        self.author = "cytube-bot"
        
        self.service: Optional[WeatherService] = None
    
    async def setup(self):
        """Set up the plugin (create service and register commands)."""
        # Load configuration
        config = self.get_config()
        api_key = config.get('api_key')
        
        if not api_key or api_key == 'your_openweathermap_api_key_here':
            self.logger.error("OpenWeatherMap API key not configured!")
            raise ValueError("Missing API key in config.json")
        
        cache_duration = config.get('cache_duration', 3600)
        rate_limit = config.get('rate_limit', 60)
        
        # Create and start service
        self.service = WeatherService(api_key, cache_duration, rate_limit)
        await self.service.start()
        
        # Provide service to other plugins
        await self.provide_service('weather', self.service)
        
        # Register commands
        await self.register_command('weather', self._handle_weather)
        await self.register_command('forecast', self._handle_forecast)
        
        self.logger.info(f"Weather plugin loaded")
    
    async def teardown(self):
        """Clean up plugin resources."""
        if self.service:
            await self.service.stop()
            self.service = None
        self.logger.info(f"Weather plugin unloaded")
    
    async def _handle_weather(self, channel: Channel, user: User, args: str):
        """Handle !weather command."""
        if not args.strip():
            await channel.send_message("❌ Please provide a location")
            await channel.send_message("Example: !weather Seattle")
            return
        
        location = args.strip()
        
        # Fetch weather data
        weather = await self.service.get_current_weather(location)
        
        if not weather:
            await channel.send_message(f"❌ Location not found: {location}")
            return
        
        # Format and send
        message = self._format_current_weather(weather)
        await channel.send_message(message)
    
    async def _handle_forecast(self, channel: Channel, user: User, args: str):
        """Handle !forecast command."""
        if not args.strip():
            await channel.send_message("❌ Please provide a location")
            await channel.send_message("Example: !forecast Seattle")
            return
        
        location = args.strip()
        
        # Fetch forecast data
        forecast = await self.service.get_forecast(location, days=3)
        
        if not forecast:
            await channel.send_message(f"❌ Location not found: {location}")
            return
        
        # Format and send
        await channel.send_message(f"📅 3-Day Forecast for {location}:")
        await channel.send_message("")
        
        for day in forecast:
            message = self._format_forecast_day(day)
            await channel.send_message(message)
            await channel.send_message("")
    
    def _format_current_weather(self, weather: dict) -> str:
        """Format current weather for display."""
        emoji = self.CONDITION_EMOJIS.get(weather['condition'], '🌤️')
        
        # Convert to Fahrenheit
        temp_f = self._c_to_f(weather['temp'])
        feels_like_f = self._c_to_f(weather['feels_like'])
        
        return (
            f"{emoji} {weather['location']}, {weather['country']}:\n"
            f"  Currently: {weather['temp']:.0f}°C ({temp_f:.0f}°F), {weather['description'].title()}\n"
            f"  Feels like: {weather['feels_like']:.0f}°C ({feels_like_f:.0f}°F)\n"
            f"  Humidity: {weather['humidity']}%\n"
            f"  Wind: {weather['wind_speed']:.0f} km/h {weather['wind_direction']}"
        )
    
    def _format_forecast_day(self, day: dict) -> str:
        """Format forecast day for display."""
        emoji = self.CONDITION_EMOJIS.get(day['condition'], '🌤️')
        
        # Day name
        day_name = day['date'].strftime('%A')
        
        # Convert to Fahrenheit
        high_f = self._c_to_f(day['temp_high'])
        low_f = self._c_to_f(day['temp_low'])
        
        return (
            f"{day_name}:\n"
            f"  {emoji} {day['description'].title()}, "
            f"High: {day['temp_high']:.0f}°C ({high_f:.0f}°F), "
            f"Low: {day['temp_low']:.0f}°C ({low_f:.0f}°F)"
        )
    
    def _c_to_f(self, celsius: float) -> float:
        """Convert Celsius to Fahrenheit."""
        return celsius * 9 / 5 + 32
```

## Testing Strategy

### Unit Tests

```python
"""Tests for weather plugin."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from plugins.weather.service import WeatherService
from plugins.weather.plugin import WeatherPlugin


@pytest.mark.asyncio
async def test_cache_hit():
    """Test that cached data is returned without API call."""
    service = WeatherService('test_key', cache_duration=600)
    await service.start()
    
    # Mock the session
    service.session.get = AsyncMock()
    
    # First call (cache miss)
    service.cache['current_seattle'] = (
        {'temp': 15, 'location': 'Seattle'},
        datetime.now()
    )
    
    # Second call (cache hit)
    result = await service.get_current_weather('Seattle')
    
    # Session should NOT be called (cache hit)
    service.session.get.assert_not_called()
    assert result['temp'] == 15


@pytest.mark.asyncio
async def test_api_error_handling():
    """Test that API errors are handled gracefully."""
    service = WeatherService('test_key')
    await service.start()
    
    # Mock 404 response
    mock_response = MagicMock()
    mock_response.status = 404
    service.session.get = AsyncMock(return_value=mock_response)
    
    result = await service.get_current_weather('InvalidCity')
    
    assert result is None


@pytest.mark.asyncio
async def test_service_provision(plugin_manager):
    """Test that WeatherService is provided to other plugins."""
    plugin = WeatherPlugin(plugin_manager)
    await plugin.setup()
    
    # Service should be registered
    service = plugin_manager.get_service('weather')
    assert service is not None
    assert isinstance(service, WeatherService)
```

### Integration Tests

```python
"""Integration tests for weather plugin."""

import pytest


@pytest.mark.asyncio
async def test_weather_command(bot, channel):
    """Test weather command through bot."""
    # Send command
    await channel.send_chat("!weather Seattle")
    
    # Wait for response
    response = await channel.wait_for_message(timeout=5.0)
    
    # Verify format
    assert "Seattle" in response
    assert "°C" in response
    assert "°F" in response


@pytest.mark.asyncio
async def test_forecast_command(bot, channel):
    """Test forecast command through bot."""
    await channel.send_chat("!forecast London")
    
    # Should get multiple messages (one per day)
    messages = []
    for _ in range(4):  # Header + 3 days
        msg = await channel.wait_for_message(timeout=5.0)
        messages.append(msg)
    
    assert any("Forecast" in msg for msg in messages)
```

### Manual Testing

1. **Basic weather:**
   ```
   !weather Seattle
   !weather London
   !weather Tokyo
   ```

2. **Forecast:**
   ```
   !forecast Seattle
   !forecast "New York"
   ```

3. **Caching (same location twice within 10 min):**
   ```
   !weather Seattle    # API call
   !weather Seattle    # Cache hit (faster)
   ```

4. **Error cases:**
   ```
   !weather InvalidCityXYZ
   !weather
   ```

5. **Hot reload:**
   - Edit config.json (change cache_duration)
   - Save
   - Verify new cache duration applied

## Architecture Validation

This plugin validates:

- ✅ **External I/O:** HTTP API calls with aiohttp
- ✅ **Service provider:** Provides WeatherService to other plugins
- ✅ **Configuration:** API key and settings from config.json
- ✅ **Caching:** TTL-based caching reduces API calls
- ✅ **Rate limiting:** Enforces API rate limits
- ✅ **Error handling:** Graceful handling of network/API errors
- ✅ **Async patterns:** Non-blocking HTTP calls

## Implementation Steps

### Step 1: Setup (30 minutes)

1. Create plugin structure
2. Add aiohttp dependency
3. Create config.json template

### Step 2: WeatherService (2.5 hours)

1. Implement HTTP client setup
2. Implement `get_current_weather()`
3. Implement `get_forecast()`
4. Add caching logic
5. Add rate limiting
6. Add helper methods

### Step 3: WeatherPlugin (1.5 hours)

1. Implement lifecycle (start/stop service)
2. Implement service provision
3. Implement `_handle_weather()`
4. Implement `_handle_forecast()`
5. Add formatting methods

### Step 4: Testing (30 minutes)

1. Unit tests
2. Integration tests
3. Manual testing

**Total:** ~5 hours

## Dependencies

Add to `requirements.txt`:

```
aiohttp>=3.8.0
```

## External Services

**OpenWeatherMap API:**

- Sign up: https://openweathermap.org/
- Free tier: 60 calls/minute, 1,000,000 calls/month
- API docs: https://openweathermap.org/api

## Design Decisions

### Why aiohttp?

- **Async:** Non-blocking HTTP calls
- **Mature:** Well-tested, widely used
- **Full-featured:** Sessions, timeouts, error handling

### Why cache for 1-3 hours?

- Weather changes slowly (hourly updates are sufficient for chat bot use)
- Reduces API calls significantly (free tier limits)
- Improves response time
- Good API citizenship (don't hammer OpenWeatherMap)
- Configurable for different needs (1 hour default, can go up to 3 hours)

### Why provide as service?

- Other plugins can use weather data
- Example: "Should I go outside?" plugin
- Demonstrates service registry pattern

---

**Estimated Implementation:** 5 hours  
**Lines of Code:** ~500 (300 service + 200 plugin)  
**External Dependencies:** aiohttp  
**Architecture Features Validated:** 7/16
