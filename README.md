# thiscovery-crm
## Purpose
Thiscovery integration with CRM (Customer Relationship Management) system.
All thiscovery interactions with HubSpot are carried out by this
stack.

## Responsibilities 

### Data storage
1. Dynamodb "HubspotEmailTemplates" table (stores configuration)
2. Dynamodb "lookups" table (stores configuration)
3. Dynamodb "notifications" table (stores events)
4. Dynamodb "tokens" table (stores authentication tokens)

### Processing
1. Notifies HubSpot of new user registrations
2. Notifies HubSpot of user login events
3. Notifies HubSpot of task signup events
4. Calls the HubSpot Single-send API to send transactional emails to thiscovery users
5. Deletes processed notifications that are older than 7 days (except emails)

## Interfaces
### Events raised
None to be processed by other stacks, though events are raised
to effect communication between lambdas in this stack.
### Events consumed
| Bus                    | Source(s)                    | Event(s)                  | Description                                                                      |
|------------------------|------------------------------|---------------------------|----------------------------------------------------------------------------------|
| Auth0                  | Auth0                        | s                         | Successful login                                                                 |
|------------------------|------------------------------| ------------------------- | -------------------------------------------------------------------------------- |
| Auth0                  | Auth0                        | ss                        | Successful signup                                                                |
| ---------------------- | ---------------------------- | -----------------------   | -------------------------------------------------------------------------------  |
| Thiscovery             | Thiscovery microservices     | transactional_email       | Triggers an email communication to a thiscovery user or valid email address      |
| ---------------------- | --------------------------   | ---------------------     | -----------------------------------------------------------------------------    |
| Thiscovery             | Thiscovery core              | task_signup               | Indicates an user has signed up for a task; triggers notification to HubSpot     |

 
### API endpoints
None


## Future direction
Possible future improvements include:
1. Use of SecretsManager instead of a "tokens" table
2. Use of ParameterStore instead of a "lookups" table
3. Use of AWS SQS (or replaying failed EventBridge events) instead of a "notifications" table