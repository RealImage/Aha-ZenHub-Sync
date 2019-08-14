# Aha-ZenHub-Sync

This is a service that is used to sync the data from Zenhub to Aha.

So basically this script helps to bring the Epics and the User stories from Zenhub to Aha.


# Tech Details

* [Python] - Aha-Zenhub scripted language
* [Heroku] - The app is installed in Heroku.
* [Google Firebase] - The database of the synced featured will be stored.


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
"Closed":"Released",```
