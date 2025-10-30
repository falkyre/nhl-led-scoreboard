"""
NHL API Client - Centralized HTTP client for all NHL API interactions.

This module provides a clean, consistent interface to the NHL API with:
- Automatic retry logic with exponential backoff
- Consistent error handling
- Proper timeout management
- Response caching support
- Comprehensive logging
- Optional structured dataclass responses
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import backoff
import httpx

if TYPE_CHECKING:
    from nhl_api.models import Game, Player, Standings

logger = logging.getLogger("scoreboard")


class NHLAPIError(Exception):
    """Base exception for NHL API errors."""
    pass


class NHLAPIClient:
    """
    Client for interacting with the NHL API.

    Provides consistent error handling, retry logic, and response parsing
    for all NHL API endpoints.
    """

    # API Base URLs
    BASE_URL = "https://api-web.nhle.com/v1/"
    STATS_URL = "https://api.nhle.com/stats/rest/en/"
    RECORDS_URL = "https://records.nhl.com/site/api/"

    # Request configuration
    DEFAULT_TIMEOUT = 5
    MAX_RETRIES = 3

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, ssl_verify: bool = True):
        """
        Initialize NHL API client.

        Args:
            timeout: Request timeout in seconds
            ssl_verify: Whether to verify SSL certificates
        """
        self.timeout = timeout
        self.ssl_verify = ssl_verify
        self._session = self._create_session()

    def _create_session(self) -> httpx.Client:
        """Create an httpx client with default configuration."""
        return httpx.Client(
            verify=self.ssl_verify,
            timeout=self.timeout,
            follow_redirects=True  # Follow redirects by default (like requests)
        )

    def _should_retry(e):
        """
        Determine if we should retry the request.

        Don't retry on:
        - 429 (rate limit) - Making more requests makes it worse
        - 4xx client errors (except 429 handled above)

        Do retry on:
        - Network errors (connection, timeout)
        - 5xx server errors
        """
        # Always retry timeouts
        if isinstance(e, httpx.TimeoutException):
            return True

        if isinstance(e, httpx.HTTPStatusError):
            # Don't retry on rate limit or client errors
            if e.response.status_code == 429:
                return False
            if 400 <= e.response.status_code < 500:
                return False
        return True

    @backoff.on_exception(
        backoff.expo,
        httpx.RequestError,
        max_tries=MAX_RETRIES,
        giveup=lambda e: not NHLAPIClient._should_retry(e),
        logger='scoreboard'
    )
    def _request_with_retry(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Internal method that makes HTTP GET request with automatic retries.

        This method is wrapped by the backoff decorator for retry logic.

        Args:
            url: Full URL to request
            params: Optional query parameters

        Returns:
            Parsed JSON response

        Raises:
            httpx.RequestError: On network/HTTP errors (will be retried by decorator)
            ValueError: On JSON parse errors (not retried)
        """
        # Log request details
        if params:
            logger.debug(f"NHL API Request: {url} (params: {params})")
        else:
            logger.debug(f"NHL API Request: {url}")

        # Make the request
        response = self._session.get(url, params=params, timeout=self.timeout)

        # Log response status
        logger.debug(f"NHL API Response: {response.status_code} ({len(response.content)} bytes)")

        response.raise_for_status()
        json_data = response.json()

        # Log successful parse
        logger.debug("NHL API: Successfully parsed JSON response")

        return json_data

    def _request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make HTTP GET request with retry logic and error handling.

        Args:
            url: Full URL to request
            params: Optional query parameters

        Returns:
            Parsed JSON response

        Raises:
            NHLAPIError: If request fails after retries
        """
        try:
            return self._request_with_retry(url, params)
        except httpx.TimeoutException as e:
            logger.error(f"NHL API Timeout after {self.MAX_RETRIES} retries: {url} (timeout: {self.timeout}s)")
            raise NHLAPIError(f"Request timed out after {self.MAX_RETRIES} retries: {url}") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"NHL API HTTP Error: {e.response.status_code} for {url}")
            if hasattr(e.response, 'text'):
                logger.debug(f"Response body: {e.response.text[:500]}")  # First 500 chars
            raise NHLAPIError(f"HTTP error {e.response.status_code}: {url}") from e
        except httpx.ConnectError as e:
            logger.error(f"NHL API Connection Error after {self.MAX_RETRIES} retries: Failed to connect to {url}")
            raise NHLAPIError(f"Connection failed after {self.MAX_RETRIES} retries: {url}") from e
        except httpx.RequestError as e:
            logger.error(f"NHL API Request Failed after {self.MAX_RETRIES} retries: {url}")
            raise NHLAPIError(f"Request failed after {self.MAX_RETRIES} retries: {url}") from e
        except ValueError as e:
            logger.error(f"NHL API JSON Parse Error: Invalid JSON from {url} - {e}")
            raise NHLAPIError(f"Invalid JSON response: {url}") from e

    # =========================================================================
    # Game Endpoints
    # =========================================================================

    def get_score_details(self, date_obj) -> Dict[str, Any]:
        """
        Get score details for a specific date.

        Args:
            date_obj: Date to get scores for (date object or string in YYYY-MM-DD format)

        Returns:
            Score details including all games for the date
        """
        # Handle both date objects and strings
        if isinstance(date_obj, str):
            # Already formatted as string
            date_str = date_obj
        else:
            # Format date object
            date_str = f"{date_obj.year}-{date_obj.month:02d}-{date_obj.day:02d}"

        url = f"{self.BASE_URL}score/{date_str}"
        return self._request(url)

    def get_game_overview(self, game_id: int) -> Dict[str, Any]:
        """
        Get detailed game overview including play-by-play.

        Args:
            game_id: NHL game ID

        Returns:
            Complete game details
        """
        url = f"{self.BASE_URL}gamecenter/{game_id}/play-by-play"
        return self._request(url)

    def get_game_status(self) -> Dict[str, Any]:
        """
        Get current game status information.

        Returns:
            Game status data
        """
        url = f"{self.BASE_URL}gameStatus"
        return self._request(url)

    # =========================================================================
    # Team Endpoints
    # =========================================================================

    def get_teams(self) -> Dict[str, Any]:
        """
        Get all NHL teams information.

        Returns:
            Dictionary of team data
        """
        url = f"{self.STATS_URL}team"
        return self._request(url)

    def get_team_schedule(self, team_code: str, season: Optional[str] = None) -> Dict[str, Any]:
        """
        Get schedule for a specific team.

        Args:
            team_code: Three-letter team code (e.g., 'TOR', 'MTL')
            season: Optional season code (e.g., '20232024'). If None, gets current season.

        Returns:
            Team schedule data
        """
        if season:
            url = f"{self.BASE_URL}club-schedule-season/{team_code}/{season}"
        else:
            url = f"{self.BASE_URL}club-schedule-season/{team_code}/now"
        return self._request(url)

    # =========================================================================
    # Player Endpoints
    # =========================================================================

    def get_player(self, player_id: int) -> Dict[str, Any]:
        """
        Get player information and statistics.

        Args:
            player_id: NHL player ID

        Returns:
            Player data including stats and biographical info
        """
        url = f"{self.BASE_URL}player/{player_id}/landing"
        return self._request(url)

    def get_skater_stats_leaders(
        self,
        category: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get current NHL skater statistics leaders.

        Args:
            category: Specific stat category. Valid options:
                - goals
                - points
                - assists
                - toi (time on ice)
                - plusMinus
                - penaltyMins
                - faceoffLeaders
                - goalsPp (powerplay)
                - goalsSh (shorthanded)
            limit: Number of results to return

        Returns:
            Leader statistics data

        Raises:
            ValueError: If category is invalid
        """
        valid_categories = {
            'goals', 'points', 'assists', 'toi', 'plusMinus',
            'penaltyMins', 'faceoffLeaders', 'goalsPp', 'goalsSh'
        }

        if category and category not in valid_categories:
            raise ValueError(
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(sorted(valid_categories))}"
            )

        params = {}
        if category:
            params['categories'] = category
        if limit:
            params['limit'] = limit

        url = f"{self.BASE_URL}skater-stats-leaders/current"
        return self._request(url, params=params)

    # =========================================================================
    # Season & Standings Endpoints
    # =========================================================================

    def get_current_season(self) -> Dict[str, Any]:
        """
        Get current season information.

        Returns:
            Current season data
        """
        url = f"{self.BASE_URL}season"
        return self._request(url)

    def get_next_season(self) -> Dict[str, Any]:
        """
        Get next season schedule information.

        Returns:
            Next season data
        """
        url = f"{self.BASE_URL}schedule/now"
        return self._request(url)

    def get_standings(self) -> Dict[str, Any]:
        """
        Get current NHL standings.

        Returns:
            Standings data
        """
        url = f"{self.BASE_URL}standings/now"
        return self._request(url)

    def get_standings_wildcard(self) -> Dict[str, Any]:
        """
        Get standings with wildcard leaders.

        Returns:
            Standings with wildcard information
        """
        url = f"{self.BASE_URL}standings/wildCardWithLeaders"
        return self._request(url)

    # =========================================================================
    # Playoff Endpoints
    # =========================================================================

    def get_playoff_data(self, season: str) -> Dict[str, Any]:
        """
        Get playoff tournament data for a season.

        Args:
            season: Season code (e.g., '20232024')

        Returns:
            Playoff bracket and series data
        """
        url = f"{self.BASE_URL}tournaments/playoffs"
        params = {
            'expand': 'round.series,schedule.game.seriesSummary',
            'season': season
        }
        return self._request(url, params=params)

    def get_series_record(self, series_code: str, season: str) -> Dict[str, Any]:
        """
        Get playoff series record from NHL Records API.

        Args:
            series_code: Series letter code (e.g., 'A', 'B', 'C')
            season: Season ID (e.g., '20232024')

        Returns:
            Series record data
        """
        url = f"{self.RECORDS_URL}playoff-series"
        params = {
            'cayenneExp': f"playoffSeriesLetter='{series_code}' and seasonId={season}"
        }
        return self._request(url, params=params)

    def get_playoff_carousel(self, season: str) -> Dict[str, Any]:
        """
        Get playoff carousel data for a season.

        Args:
            season: Season code (e.g., '20232024')

        Returns:
            Playoff carousel data including rounds and series
        """
        url = f"{self.BASE_URL}playoff-series/carousel/{season}"
        return self._request(url)

    # =========================================================================
    # Structured Data Methods (Optional - returns dataclasses)
    # =========================================================================

    def get_games_structured(self, date_obj) -> List['Game']:
        """
        Get games for a date as structured Game objects.

        Args:
            date_obj: Date to get games for

        Returns:
            List of Game dataclass instances
        """
        from nhl_api.models import Game

        data = self.get_score_details(date_obj)
        games = []

        for game_data in data.get('games', []):
            try:
                games.append(Game.from_dict(game_data))
            except Exception as e:
                logger.warning(f"Failed to parse game data: {e}")
                continue

        return games

    def get_standings_structured(self) -> 'Standings':
        """
        Get current standings as a structured Standings object.

        Returns:
            Standings dataclass instance with conferences and divisions
        """
        from nhl_api.models import Standings

        data = self.get_standings()
        return Standings.from_dict(data)

    def get_player_structured(self, player_id: int) -> 'Player':
        """
        Get player information as a structured Player object.

        Args:
            player_id: NHL player ID

        Returns:
            Player dataclass instance
        """
        from nhl_api.models import Player

        data = self.get_player(player_id)
        return Player.from_dict(data)

    def close(self):
        """Close the session and cleanup resources."""
        if self._session:
            self._session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
