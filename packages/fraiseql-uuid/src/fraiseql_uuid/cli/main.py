"""CLI commands for fraiseql-uuid."""

import sys

import click

from fraiseql_uuid import Pattern, UUIDGenerator, UUIDValidator


@click.group()
@click.version_option(package_name="fraiseql-uuid")
def cli() -> None:
    """fraiseql-uuid - UUID v4 compliant pattern with encoded metadata."""
    pass


@cli.command()
@click.option("--table", required=True, help="Table code (6 digits)")
@click.option("--instance", type=int, help="Instance number (for single UUID)")
@click.option("--count", type=int, help="Number of UUIDs to generate (batch mode)")
@click.option("--seed-dir", type=int, default=21, help="Seed directory (default: 21)")
@click.option("--function", "func", type=int, default=0, help="Function code (default: 0)")
@click.option("--scenario", type=int, default=0, help="Scenario code (default: 0)")
@click.option("--test-case", type=int, default=0, help="Test case number (default: 0)")
def generate(
    table: str,
    instance: int | None,
    count: int | None,
    seed_dir: int,
    func: int,
    scenario: int,
    test_case: int,
) -> None:
    """Generate UUID(s) with encoded metadata."""
    pattern = Pattern()

    # Validate mutually exclusive options
    if instance is not None and count is not None:
        click.echo("Error: --instance and --count are mutually exclusive", err=True)
        sys.exit(1)

    if instance is None and count is None:
        click.echo("Error: Either --instance or --count is required", err=True)
        sys.exit(1)

    # Single UUID generation
    if instance is not None:
        uuid = pattern.generate(
            table_code=table,
            seed_dir=seed_dir,
            function=func,
            scenario=scenario,
            test_case=test_case,
            instance=instance,
        )
        click.echo(uuid)
        return

    # Batch generation
    if count is not None:
        gen = UUIDGenerator(
            pattern,
            table_code=table,
            seed_dir=seed_dir,
            function=func,
            scenario=scenario,
            test_case=test_case,
        )
        uuids = gen.generate_batch(count)
        for uuid in uuids:
            click.echo(uuid)


@cli.command()
@click.argument("uuid")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def decode(uuid: str, output_json: bool) -> None:
    """Decode UUID into components."""
    pattern = Pattern()

    try:
        decoded = pattern.decode(uuid)

        if output_json:
            import json

            click.echo(json.dumps(decoded.components, indent=2))
        else:
            click.echo(f"UUID: {decoded.raw_uuid}")
            click.echo(f"  table_code: {decoded['table_code']}")
            click.echo(f"  seed_dir:   {decoded['seed_dir']}")
            click.echo(f"  function:   {decoded['function']}")
            click.echo(f"  scenario:   {decoded['scenario']}")
            click.echo(f"  test_case:  {decoded['test_case']}")
            click.echo(f"  instance:   {decoded['instance']}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("uuid")
@click.option("--quiet", "-q", is_flag=True, help="Only output result (0=valid, 1=invalid)")
def validate(uuid: str, quiet: bool) -> None:
    """Validate UUID format."""
    pattern = Pattern()
    validator = UUIDValidator(pattern)

    result = validator.validate(uuid)

    if quiet:
        sys.exit(0 if result.valid else 1)

    if result.valid:
        click.echo(f"✓ Valid UUID: {uuid}")
        sys.exit(0)
    else:
        click.echo(f"✗ Invalid UUID: {result.error}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
