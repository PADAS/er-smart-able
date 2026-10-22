# Statuses

## A load

| Status | Meaning |
|---|---|
| <code>planning</code> | The plan is being made. Writes nothing. |
| <code>planned</code> | The plan is ready to read and confirm. |
| <code>queued</code> | Confirmed; the run has been asked for and is about to start. |
| <code>running</code> | The run is working through its stages. The page updates itself every few seconds. |
| <code>continuing</code> | The run reached the 22-hour limit and handed over to a new execution of itself. See *Long runs and continuation*. |
| <code>needs_attention</code> | The run stopped at a blocking finding, or finished with patrols that failed. Read the findings, fix the site, press **Continue**. |
| <code>done</code> | Every patrol is on the site. |
| <code>failed</code> | The job hit an error it could not recover from. The error and the log are on the page. After fixing the cause, press **Plan again**; the new plan shows what is left and offers Confirm. (Continue is only for a load that stopped on findings or whose job was killed.) |

## A stage

| Status | Meaning |
|---|---|
| pending | Not reached yet in this execution. |
| running | In progress, with the time it has taken so far. |
| done | Finished, with how long it took and what it did. |
| stopped | The stop rule ended the run here: a blocking finding after this stage. |
| failed | An error in this stage ended the run. |
| interrupted | The job was killed before it could report; its hold has lapsed and **Continue** is available. |
| not reached | A later stage of a run that stopped or failed earlier. |

## The heartbeat

Under the stage table, while a load is active, one line says how long this execution has been running and how long since the job last reported. The job reports at every stage boundary and at least every thirty seconds during the import, so a "last reported" time that keeps growing past a few minutes means the job is stuck or gone.
