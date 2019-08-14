# Aha-ZenHub-Sync

This is a service that is used to sync the data from Zenhub to Aha.

So basically this script helps to bring the Epics and the User stories from Zenhub to Aha.


# Tech Details

| Details | Spec
| ------ | ------ |
| Aha-Zenhub scripted language | Python |
| The app is installed in Heroku | Heroku |
| The database of the synced featured will be stored | Google Firebase |


The below are the mapping for the Epic's that are present in Zenhub to be represented in Aha

```"Whislist":"Whislist",
"User Stories":"Backlog",
"Epics": "Backlog",
"Issues": "Backlog",
"Next Iteration":"Ready for Dev",
"This Iteration":"Ready for Dev",
"In Dev":"In Dev",
"Epics In Dev":"In Dev",
"Parked":"Parked",
"Pending Review":"In Dev",
"Review Done":"Ready for QA",
"Pending Fixes":"In QA",
"Ready for QA":"Ready for QA",
"In QA":"In QA",
"Pending Automation":"In QA",
"Ready for Design Review":"In QA",
"Ready for Release":"Ready for Release",
"Closed":"Released",
> The pipelines are configurable

# Configuration to be done for each products
```"Zenhub_Domain":"https://api.zenhub.io",
"Aha_Domain":"https://qubecinema.aha.io",
"Zenhub_repo_Id":"*******",
"product_id":"************",
"product_ref":"MB",
"repo_name":"Realimage/******",
"ndurance_key":"The Key that is generated from Firebase",
"update_release_dates": false,
"Track_due_date": true,
"features_source_of_release_date": "github",
"AHA_TOKEN":"Token",
"ZENHUB_TOKEN":"Token",
"GITHUB_TOKEN":"Token",
"Endurance_Source":"Firebase Source 2",
"slack_channel":"Slack Channel ID to send the report",
"Endurance_Source_3":"Firebase Source 2"
