# Changelog

## [0.2.0](https://github.com/fraiseql/fraiseql-seed/compare/fraiseql-data-v0.1.4...fraiseql-data-v0.2.0) (2026-05-27)


### Features

* **builder:** integrate group value injection into _generate_rows() ([82bea92](https://github.com/fraiseql/fraiseql-seed/commit/82bea9287db541b3e05338e9aac514dab7d19246))
* **ci:** Add comprehensive quality-gate workflow [GREENFIELD] ([5b2027b](https://github.com/fraiseql/fraiseql-seed/commit/5b2027bd5b972c98cf9c4e47e915217b98dbcaf7))
* **cli:** Add export command with multi-format support and SQL injection protection ([ba09e87](https://github.com/fraiseql/fraiseql-seed/commit/ba09e87a5ed3a005bf0064571d9990f37240fc93))
* **cli:** P2 polish - configuration, formatters, and logging ([80979d0](https://github.com/fraiseql/fraiseql-seed/commit/80979d0fb3f26314e35955959c9b44d19ed1be2e))
* **dependency:** relax validate_plan() to accept overridden FK deps ([0a49287](https://github.com/fraiseql/fraiseql-seed/commit/0a49287a604f17d2d98881c6c1760092b25a9e5a))
* **fraiseql-data:** Implement Phase 1 Zero-Guessing Core [GREEN] ([c3cd03b](https://github.com/fraiseql/fraiseql-seed/commit/c3cd03b8fa11274f614818d9c62149aa31fc478c))
* **fraiseql-data:** Implement Phase 2 features [GREEN] ([1afe754](https://github.com/fraiseql/fraiseql-seed/commit/1afe7549f8c00c1f9714bd75037584520d3d5964))
* **fraiseql-data:** Implement Phase 3 features [GREEN] ([a4ef432](https://github.com/fraiseql/fraiseql-seed/commit/a4ef432148efdea66fa9ed731597fc33d331d8a3))
* **fraiseql-data:** Implement Phase 4 features [GREEN] ([661558c](https://github.com/fraiseql/fraiseql-seed/commit/661558c5e5775430604e0b15beaf08bb9018af52))
* **fraiseql-data:** Implement Phase 5-GREEN auto-dependency resolution [GREEN] ([3ea2eec](https://github.com/fraiseql/fraiseql-seed/commit/3ea2eecda0721c3b4d54abee74f0ef10f2bc2468))
* **fraiseql-data:** Implement seed common baseline system [GREEN] ([2407328](https://github.com/fraiseql/fraiseql-seed/commit/2407328737ab1c30cacb13f3b062c077693bbac9))
* **fraiseql-data:** Implement Trinity extension integration for deterministic PK allocation ([42ca235](https://github.com/fraiseql/fraiseql-seed/commit/42ca235f9a921490e63a26a5cc48254849c7a8ea))
* **generators:** add identity and serial column detection and skipping ([ec2270a](https://github.com/fraiseql/fraiseql-seed/commit/ec2270af0da4ff21b10024f4d8cdb25102cfec5a))
* **generators:** add type-aware generators for 15+ PostgreSQL types ([912571e](https://github.com/fraiseql/fraiseql-seed/commit/912571ec77633a2488d5565d713fb813f3d7fc6b))
* **groups:** add ColumnGroup dataclass and GroupRegistry detection ([35c01f4](https://github.com/fraiseql/fraiseql-seed/commit/35c01f4eab7cc89f41046c3932f9e9724eb77ae9))
* **groups:** add generate_address and generate_person generators ([c84fe3c](https://github.com/fraiseql/fraiseql-seed/commit/c84fe3c3042e0eabbe2e1e97443df0e159867fb1))
* **groups:** add geo generator, UNIQUE retry, SeedPlan groups field ([790c2fd](https://github.com/fraiseql/fraiseql-seed/commit/790c2fd5e89968bfe58c9de18d272b39787e973f))
* **groups:** enrich generator context with _instance and _table_columns ([9cbacf2](https://github.com/fraiseql/fraiseql-seed/commit/9cbacf28982b3e3056559432736f2fc228cf9ddd))
* Initial fraiseql-seed monorepo structure ([de13343](https://github.com/fraiseql/fraiseql-seed/commit/de13343aeab43715cf8f5c08e6ef0f715b030d4e))
* **tests:** add integration tests for all PG types, fix 3 bugs found ([9e9a34d](https://github.com/fraiseql/fraiseql-seed/commit/9e9a34d70e5d1c45328be6c2e52e816b47a171b9))
* **tooling:** enable full ruff ruleset and bump target-version to py312 ([4a8b841](https://github.com/fraiseql/fraiseql-seed/commit/4a8b8419a67c285704deadd1eb1c29f1307659c0))
* **tooling:** migrate from mypy to ty and update CI ([fc5a893](https://github.com/fraiseql/fraiseql-seed/commit/fc5a893a6a9452f7a9c8c4476b01cddfb981811f))


### Bug Fixes

* **builder:** apply overrides before FK resolution in _generate_rows ([5796e19](https://github.com/fraiseql/fraiseql-seed/commit/5796e196a2e7b1626b650d836e16f1823787fb56))
* **builder:** suppress seed_common warning noise ([4ddd46a](https://github.com/fraiseql/fraiseql-seed/commit/4ddd46ad24842e7c5571c50c65973ca736e0e00b))
* **ci:** fix build paths in deploy, fix env-leaking test fixtures ([6ce85f0](https://github.com/fraiseql/fraiseql-seed/commit/6ce85f0b20041277807f65cb954b348a0c128bfa))
* **ci:** Fix test database connection and CLI type checking [GREENFIELD] ([3e6e404](https://github.com/fraiseql/fraiseql-seed/commit/3e6e4046414274dfdd66921336bf8ff8ad19e8eb))
* **export:** use psycopg.sql.Literal for SQL escaping, improve import types ([ff7c673](https://github.com/fraiseql/fraiseql-seed/commit/ff7c673093e6df22403f5a5671d2280348f30c9a))
* **fraiseql-data:** Correct FK naming to follow fraiseQL conventions [REFACTOR] ([458d40a](https://github.com/fraiseql/fraiseql-seed/commit/458d40a904d0fbc2731a5f9a2b99996bb8b48d4f))
* **fraiseql-data:** Use modern IDENTITY syntax instead of BIGSERIAL [REFACTOR] ([b5be2e1](https://github.com/fraiseql/fraiseql-seed/commit/b5be2e1652cb6d22a8c2bbc4f61829e7b4eac5bf))
* **generator:** respect numeric(p,s) precision bounds ([59de9fb](https://github.com/fraiseql/fraiseql-seed/commit/59de9fb3a44631480925f8e1bc0e605b342f9f6c))
* **introspection:** pass numeric precision/scale to pg_type string ([8887f2e](https://github.com/fraiseql/fraiseql-seed/commit/8887f2edf6844d4594be4d498e8f6eb194ab92c0))


### Performance

* COPY protocol, fast generators, and Faker pooling ([377f2f4](https://github.com/fraiseql/fraiseql-seed/commit/377f2f447fc83f24ec614735e7c80469522dd546))


### Refactors

* **cli:** P1 architecture foundation - separation of concerns ([02a12af](https://github.com/fraiseql/fraiseql-seed/commit/02a12af83ba5eb7542f2c780942d174a5ae077a5))
* finalize Phase 06 — API fixes, archaeology removal, README rewrite ([ea2305e](https://github.com/fraiseql/fraiseql-seed/commit/ea2305ebe1f4917790e927ea4668a3e40d79150c))
* **fraiseql-data:** Add error handling, validation, and comprehensive docs [REFACTOR] ([f1ad546](https://github.com/fraiseql/fraiseql-seed/commit/f1ad546fe57bc21a16da4f7b3f5581fe2e355ef6))
* **fraiseql-data:** Clean up seed common implementation [REFACTOR] ([51ec7b7](https://github.com/fraiseql/fraiseql-seed/commit/51ec7b7d953b9a1fba2a9930f097fe1d9ddcb583))
* **fraiseql-data:** Extract auto-deps logic to dedicated module [REFACTOR] ([a7018a1](https://github.com/fraiseql/fraiseql-seed/commit/a7018a1130c86f476efec45e5f500b91b2a4f97d))
* **fraiseql-data:** Phase 2 code quality improvements [REFACTOR] ([cbbb3b6](https://github.com/fraiseql/fraiseql-seed/commit/cbbb3b638e275523b2c4e74c4a413f20fa9a60f4))
* **fraiseql-data:** Phase 4 code quality improvements [REFACTOR] ([22f7b25](https://github.com/fraiseql/fraiseql-seed/commit/22f7b25e5cc41543298b44a3604fe01563e262e5))
* quality hardening — psycopg.sql, dead code removal, type safety ([f9d8565](https://github.com/fraiseql/fraiseql-seed/commit/f9d85658e0fec53f105a19d4fd3f54d92065b71a))


### Documentation

* **badges:** Add comprehensive CI/CD and quality badges to READMEs [GREENFIELD] ([ce33a14](https://github.com/fraiseql/fraiseql-seed/commit/ce33a14c7d959edc69a5fdb6054234130c28dba4))
* document override priority, numeric precision, and warning behavior ([523176b](https://github.com/fraiseql/fraiseql-seed/commit/523176b4f7af453d0866764300602916ccc30776))
* **fraiseql-data:** Add Phase 6 seed common documentation [QA] ([a16c626](https://github.com/fraiseql/fraiseql-seed/commit/a16c626a1cdba2138a4c87e38dbf9da037df63a4))
* **fraiseql-data:** Add v0.1.0 release notes [GREENFIELD] ([b33b11b](https://github.com/fraiseql/fraiseql-seed/commit/b33b11bc9c6ac46fb0ca43a72c4a63e82b4cae56))
* **readme:** Clean up broken links and references ([1c0577d](https://github.com/fraiseql/fraiseql-seed/commit/1c0577de7cc8e36535118fa014e82f2cd98c4e55))
* update references from mypy to ty, py311 to py312 ([4cc6a83](https://github.com/fraiseql/fraiseql-seed/commit/4cc6a83d0b67d5ac60e2a6215108258b16cd8dfb))
