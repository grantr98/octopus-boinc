# octopus-boinc
This is a functional but POC of a Python function to automatically check the Octopus Agile API for current tariff information, then automatically run BOINC if the price is below the set threshold.

A sample .env file is enumerated as env.sample, and requires an API key and tariff information available at https://octopus.energy/dashboard/developer/.

Octopus REST API docs are available at https://octopus.com/docs/octopus-rest-api.

The boinccmd variables must be set to where your BOINC installation resides.
