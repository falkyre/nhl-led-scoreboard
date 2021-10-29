# Changelog

## [1.6.0](https://www.github.com/falkyre/nhl-led-scoreboard/compare/v1.5.7...v1.6.0) (2021-10-29)


### Features

* **image:** Add call to stop the sb_splash.service if running.  This is part of the upcoming fully built pi image ([05564d0](https://www.github.com/falkyre/nhl-led-scoreboard/commit/05564d098158860541e74fa5db32131b2fc198c7))
* **image:** Add call to stop the sb_splash.service if running.  This is part of the upcoming fully built pi image ([ddb192f](https://www.github.com/falkyre/nhl-led-scoreboard/commit/ddb192fe81eb5eeef28a4e0fadc5129f39b2d321))
* **workflow:** add create release workflow for beta and master branches ([576409a](https://www.github.com/falkyre/nhl-led-scoreboard/commit/576409afb65b2e9dc2f1cc52e68a552a37833a83))
* **workflow:** change changelog creation ([aa790f6](https://www.github.com/falkyre/nhl-led-scoreboard/commit/aa790f6a30df027256110f2bf862db7f43b7afaf))
* **workflow:** change changelog creation ([6426967](https://www.github.com/falkyre/nhl-led-scoreboard/commit/64269677b66864ed0c444137e9c8e16ca137985f))
* **workflow:** change changelog creation ([1358683](https://www.github.com/falkyre/nhl-led-scoreboard/commit/1358683cc9babb8315a7abb4a7fb3f3250bfc9eb))
* **workflow:** change changelog creation ([e1af5aa](https://www.github.com/falkyre/nhl-led-scoreboard/commit/e1af5aa2eaf24ce87991659e2acfa1eaa1748538))
* **workflow:** change changelog creation ([31d40d9](https://www.github.com/falkyre/nhl-led-scoreboard/commit/31d40d94417686ec20012ed563e48e9af4126109))
* **workflow:** change changelog creation ([2c06d62](https://www.github.com/falkyre/nhl-led-scoreboard/commit/2c06d629b5b5113f1833e3062ea66034a2053461))
* **workflow:** change changelog creation ([50312dd](https://www.github.com/falkyre/nhl-led-scoreboard/commit/50312dd98d5856b81d404f085bf493665e881cae))
* **workflows:** add release-please workflow to beta branch ([7422be2](https://www.github.com/falkyre/nhl-led-scoreboard/commit/7422be2056f114c546ac8348df70bb41375f3522))
* **workflows:** add release-please workflow to beta branch ([a63f070](https://www.github.com/falkyre/nhl-led-scoreboard/commit/a63f07025bc53678d2b12b414bf04e48a1ea58c3))
* **workflow:** update VERSION file on tag push ([3ab5641](https://www.github.com/falkyre/nhl-led-scoreboard/commit/3ab56415e7f4353b428edefb37797434b915dd2a))
* **workflow:** update VERSION file on tag push ([badb61b](https://www.github.com/falkyre/nhl-led-scoreboard/commit/badb61b4abc790e9e4549f621e6daf5bad06ec5f))


### Bug Fixes

* **apt-requirements:** added dbus for dietpi users ([14aaf5d](https://www.github.com/falkyre/nhl-led-scoreboard/commit/14aaf5d1358a59cd9f1083fc2d276bf34f5c6e39))
* **config:** Added 2021 season division "north", "west", "east"  in the config.shema ([241e1c1](https://www.github.com/falkyre/nhl-led-scoreboard/commit/241e1c1bc3b56801bb92fe6ddd0ab7f1b3e6666a))
* **config:** Update sample config to be as simple as possible to create a base config.json without any of the extra features on ([d2eef0a](https://www.github.com/falkyre/nhl-led-scoreboard/commit/d2eef0a12a246f7e2e97ca9a586fc53dff9dea0a))
* **library version:** updated version of Pillow to 8.1.1 as previous version had security vulnerabilities ([b4e1299](https://www.github.com/falkyre/nhl-led-scoreboard/commit/b4e1299c1350668dece1d892529e39d29bb43f1a))
* **location:** fix(location):  ([5a9ea02](https://www.github.com/falkyre/nhl-led-scoreboard/commit/5a9ea02d1faaf0f92c1730e98a4c555e93c75b34))
* **location and scripts:** location now handles caching the file better if you already have a location saved in the config.json.  Added code to change the ownership of the locatgion.json file from root user.  updated the sb-upgrade script so it handles looking for changes between releases better ([c3686a0](https://www.github.com/falkyre/nhl-led-scoreboard/commit/c3686a061c95636e08937726d62467debcc0dba0))
* **location:** Add fallback to using timezone and the lat/lon from the zoneinfo database to set location.  If that fails, then ultimate default is Tragically Hip ([7bc390a](https://www.github.com/falkyre/nhl-led-scoreboard/commit/7bc390a79066485d78970564674c41f4627ad1eb))
* **location:** Changed message to reflect location loaded from cache and added location.json to .gitignore ([1a46f90](https://www.github.com/falkyre/nhl-led-scoreboard/commit/1a46f9092572e547165866a16a0c0c1ba3f154bb))
* **location:** Changed message to reflect location loaded from cache and how old cahce is.  Added message for reloading cache ([4b54907](https://www.github.com/falkyre/nhl-led-scoreboard/commit/4b5490735e5b2e7d9fcdafc0bb6712e200baf8a7))
* **location:** Changed message to reflect location loaded from cache and how old cahce is.  Added message for reloading cache ([0d305d9](https://www.github.com/falkyre/nhl-led-scoreboard/commit/0d305d9f87cef0809ec13cf804b051b7d8d7e3a5))
* **nhl_setup:** Add back in fuinctionality to create a simple config by only asking for a single team.  Creates the json based on the config.json.sample ([92f2e41](https://www.github.com/falkyre/nhl-led-scoreboard/commit/92f2e41f7f63000949dcf2bb950190cb627801d1))
* **nhl_setup:** add exit codes so the nhl_setup script can be used by a bash script ([7efe0f2](https://www.github.com/falkyre/nhl-led-scoreboard/commit/7efe0f26e75e597fb36f9eab853df31669f19477))
* **nhl_setup:** add exit codes so the nhl_setup script can be used by a bash script ([5d4a990](https://www.github.com/falkyre/nhl-led-scoreboard/commit/5d4a990d164f170a7ef109f7dd4c96c42cee3bca))
* **nhl_setup:** removed covid19 boards from setup.  Removed covid19 from schema and sample json file ([2389c8d](https://www.github.com/falkyre/nhl-led-scoreboard/commit/2389c8d5d54bd91ed20a0202f439a62df5810d47))
* **requirements:** fix(requirements):  ([d1b9498](https://www.github.com/falkyre/nhl-led-scoreboard/commit/d1b9498484d26da666c71e2c44984e2a8b805018))
* **scripts:** Run bash scripts through shellcheck to clean them up ([f9ac530](https://www.github.com/falkyre/nhl-led-scoreboard/commit/f9ac530c62ed596153dc48bd0d2cc29176107b4c))
* **seriesticker, playoff feature:** Now the score of each games for each series are stored and reused instead of calling the API each refresh of the board. ([14efd6c](https://www.github.com/falkyre/nhl-led-scoreboard/commit/14efd6c19a0fdb629a446cd257ba242fe5de1ccf))
* **seriesticker, playoff features:** handle partial game overview of games in series. ([f715b33](https://www.github.com/falkyre/nhl-led-scoreboard/commit/f715b331f0f9daaab6678254547333cf44afd828))
* **workflow:** add version.txt for release-please workflow ([58c5f84](https://www.github.com/falkyre/nhl-led-scoreboard/commit/58c5f8497e655ef1b964993ba3430bec553c6865))
* **workflow:** change changelog creation ([d09ca6c](https://www.github.com/falkyre/nhl-led-scoreboard/commit/d09ca6c322fcf8225b4edcdf70044c36161450a3))
* **workflow:** set workflow to simple ([aa31817](https://www.github.com/falkyre/nhl-led-scoreboard/commit/aa31817605f1b0e29108013af11526b40b274cbe))
* **workflows:** remove package.json ([925760b](https://www.github.com/falkyre/nhl-led-scoreboard/commit/925760b18ac4229731c0abe0e59ccf359cd7525a))
