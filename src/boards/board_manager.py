"""
BoardManager handles the lifecycle of board instances.

Responsibilities:
- Lazy initialization of boards (only create instances when needed)
- Track which boards are initialized vs available
- Handle cleanup when boards are removed from config
- Sync board state with config changes
"""

import logging

debug = logging.getLogger("scoreboard")


class BoardManager:
    def __init__(self, boards_registry):
        """
        Initialize the BoardManager.

        Args:
            boards_registry: The Boards instance that handles discovery/registration
        """
        self.boards_registry = boards_registry
        self._initialized_boards = {}  # board_id -> instance
        self._active_board_ids = set()  # boards currently in config

    def render_board(self, board_id: str, data, matrix, sleepEvent):
        """
        Render a board by ID with automatic lazy initialization.

        Args:
            board_id: The board identifier
            data: Application data object
            matrix: Display matrix object
            sleepEvent: Threading event for sleep/wake control

        Returns:
            Result of the board's render() or draw() method

        Raises:
            ValueError: If board_id is not found in registry
        """
        if board_id not in self.boards_registry._boards:
            raise ValueError(
                f"Board '{board_id}' not found. Available boards: {', '.join(self.boards_registry._boards.keys())}"
            )

        # Lazy initialization: create instance only if not already initialized
        if board_id not in self._initialized_boards:
            board_class = self.boards_registry._boards[board_id]
            self._initialized_boards[board_id] = board_class(data, matrix, sleepEvent)
            debug.info(f"BoardManager: Initialized board '{board_id}'")
        else:
            debug.debug(f"BoardManager: Using cached instance for board '{board_id}'")

        # Mark as active (used for tracking)
        self._active_board_ids.add(board_id)

        # Call the appropriate method (render() or draw())
        board_instance = self._initialized_boards[board_id]
        if hasattr(board_instance, 'render'):
            return board_instance.render()
        elif hasattr(board_instance, 'draw'):
            return board_instance.draw()
        else:
            debug.error(f"Board '{board_id}' has neither render() nor draw() method")
            return None

    def initialize_board(self, board_id: str, data, matrix, sleepEvent):
        """
        Explicitly initialize a board without rendering it.

        Useful for boards that require early initialization (e.g., background data fetching).

        Args:
            board_id: The board identifier
            data: Application data object
            matrix: Display matrix object
            sleepEvent: Threading event for sleep/wake control

        Returns:
            The board instance, or None if initialization failed
        """
        if board_id not in self.boards_registry._boards:
            debug.error(f"BoardManager: Cannot initialize unknown board '{board_id}'")
            return None

        if board_id in self._initialized_boards:
            debug.debug(f"BoardManager: Board '{board_id}' already initialized")
            return self._initialized_boards[board_id]

        try:
            board_class = self.boards_registry._boards[board_id]
            self._initialized_boards[board_id] = board_class(data, matrix, sleepEvent)
            debug.info(f"BoardManager: Explicitly initialized board '{board_id}'")
            return self._initialized_boards[board_id]
        except Exception as e:
            debug.error(f"BoardManager: Failed to initialize board '{board_id}': {e}")
            return None

    def cleanup_board(self, board_id: str):
        """
        Cleanup and unload a specific board.

        Args:
            board_id: The board identifier to cleanup
        """
        if board_id in self._initialized_boards:
            board = self._initialized_boards[board_id]
            if hasattr(board, "cleanup"):
                try:
                    board.cleanup()
                    debug.info(f"BoardManager: Called cleanup() for board '{board_id}'")
                except Exception as e:
                    debug.error(f"BoardManager: Error during cleanup of board '{board_id}': {e}")

            del self._initialized_boards[board_id]
            debug.info(f"BoardManager: Unloaded board '{board_id}'")

        self._active_board_ids.discard(board_id)

    def sync_with_config(self, config_board_lists: list):
        """
        Synchronize board state with current config.

        This compares the boards currently in config with initialized boards,
        and cleans up any boards that are no longer in the config.

        Args:
            config_board_lists: List of board ID lists from config
                               (e.g., [boards_off_day, boards_scheduled, ...])
        """
        # Flatten all config board lists to get unique board IDs currently in config
        config_board_ids = set()
        for board_list in config_board_lists:
            if board_list:
                config_board_ids.update(board_list)

        # Find boards that are initialized but no longer in config
        removed_boards = set(self._initialized_boards.keys()) - config_board_ids

        if removed_boards:
            debug.info(f"BoardManager: Config sync - removing boards no longer in config: {removed_boards}")
            for board_id in removed_boards:
                self.cleanup_board(board_id)

        # Update active board IDs
        self._active_board_ids = config_board_ids.copy()

        debug.debug(f"BoardManager: Config sync complete. Active boards: {self._active_board_ids}")

    def get_initialized_boards(self) -> list:
        """
        Get list of currently initialized board IDs.

        Returns:
            List of board IDs that have been initialized
        """
        return list(self._initialized_boards.keys())

    def get_active_boards(self) -> set:
        """
        Get set of board IDs that are currently active in config.

        Returns:
            Set of board IDs marked as active
        """
        return self._active_board_ids.copy()

    def is_board_initialized(self, board_id: str) -> bool:
        """
        Check if a board is currently initialized.

        Args:
            board_id: The board identifier

        Returns:
            True if board is initialized, False otherwise
        """
        return board_id in self._initialized_boards

    def clear_all_boards(self):
        """
        Cleanup and unload all initialized boards.
        """
        debug.info("BoardManager: Clearing all initialized boards")
        board_ids = list(self._initialized_boards.keys())
        for board_id in board_ids:
            self.cleanup_board(board_id)

        self._active_board_ids.clear()
        debug.info("BoardManager: All boards cleared")
