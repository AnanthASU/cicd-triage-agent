from triage_agent import generate_triage_report


def test_jest_failure_classification():
    log = """
    FAIL src/components/MyComponent.test.tsx
    TestingLibraryElementError: Unable to find an element with the text: Submit
    expect(received).toBeInTheDocument()
    """
    report = generate_triage_report(log, "jest.log")
    assert report.category.key == "FRONTEND_TEST_FAILURE"


def test_dotnet_failure_classification():
    log = """
    Build FAILED.
    Program.cs(10,15): error CS1061: 'Estimate' does not contain a definition for 'ProfileId'
    """
    report = generate_triage_report(log, "dotnet.log")
    assert report.category.key == "DOTNET_BUILD_FAILURE"


def test_schema_failure_classification():
    log = """
    schema validation failed: required property reviewerOrgCd is missing
    XML validation failed against MCEProfile.xsd
    """
    report = generate_triage_report(log, "schema.log")
    assert report.category.key == "SCHEMA_OR_CONTRACT_FAILURE"
