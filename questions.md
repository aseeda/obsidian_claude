# Obsidian-Claude Automation Tool - Design Questions

Please answer the following questions to help define the requirements for the tool.

## 1. Note Discovery

**Q1.1:** What timeframe should define "recently modified"?
- [ ] Last hour
- [ ] Last 24 hours
- [x] Last week
- [ ] Configurable (specify default: _______)
- [ ] Other: ___________

**Q1.2:** Should the tool track processed notes to avoid re-processing the same request?
- [ x] Yes, track and skip already processed requests
- [ ] No, re-process every time
- [ ] Other: ___________

**Answer:**


## 2. Request Detection

**Q2.1:** Should "@claude" matching be case-sensitive?
- [x ] Case-sensitive (only @claude)
- [ ] Case-insensitive (@Claude, @CLAUDE, etc.)

**Q2.2:** Should the tool support syntax variants?
- [ ] Only `@claude text`
- [ ] Also support `@claude: text`
- [ ] Also support `@claude - text`
- [x ] All of the above

**Q2.3:** How should processed requests be marked to prevent re-execution?
- [x ] Replace `@claude` with `@claude-done` or similar
- [ ] Maintain external database of processed requests
- [ ] Add hidden metadata to notes
- [ ] Don't track, allow re-processing
- [ ] Other: ___________

**Answer:**


## 3. Request Extraction

**Q3.1:** Should requests support multiple lines?
- [ ] Only same-line text after @claude
- [x ] Support multi-line requests

**Q3.2:** If multi-line is supported, what syntax should be used?
- [ ] Indented lines following @claude
- [ ] Code blocks following @claude
- [ ] YAML front-matter style
- [ x] Other: ___________

**Answer:**
Assume the request is in either in one line or within triple double quotes, e.g.  """this is a multi line
comment"""

## 4. Tool Authorization

**Q4.1:** What tool categories should be allowed? (Check all that apply)
- [ x] Read files within vault
- [x ] Search within vault
- [x ] Web search (informational)
- [x ] Web fetch (specific URLs)
- [ x] Write new notes in vault
- [ ] Modify existing notes in vault
- [ ] Execute read-only bash commands
- [ ] Other: ___________

**Q4.2:** Should tool permissions be configurable?
- [ ] Globally (same for all notes)
- [ x ] Per vault
- [ ] Per note (via front-matter or tags)
- [ ] Not configurable (hardcoded)

**Answer:**


## 5. Response Format

**Q5.1:** How should responses be formatted in the note?
- [ ] Plain text with markdown separator (---)
- [ ] Obsidian callout blocks (e.g., `> [!ai] Claude Response`)
- [ ] HTML comments (hidden in reading view)
- [ ] Separate section under specific heading
- [ ] Other: ___________

**Answer:**
Instead of appending to the same note the full answer, create a new note with the format "<source_note>_response_<timestamp>.md" and hyperlink to it using Obsidian's format, e.g. if the new note is called "test_response_20260227_153045.md" then the agent should add [[test_response_20260227_153045]]

**Q5.2:** Should responses include timestamps?
- [x ] Yes, include timestamp for each response
- [ ] No, skip timestamps
- [ ] Optional/configurable

**Answer:**


## 6. Implementation Approach

**Q6.1:** What execution environment should be used?
- [ ] Python script with MCP client
- [ ] Node.js/TypeScript tool
- [ ] Obsidian plugin (JavaScript)
- [ ] Other: ___________

**Answer:**
I want to share this widely on GitHub, which do you recommend? 

**Q6.2:** How should the tool run?
- [ ] Daemon/service (continuous monitoring)
- [ ] CLI tool (manual trigger)
- [x ] Scheduled task (cron/systemd timer)
- [ ] Triggered by Obsidian events (if plugin)
- [ ] Other: ___________



## 7. Operational Details

**Q7.1:** How often should notes be checked for @claude requests?
- [ ] Every few seconds (continuous)
- [ ] Every minute
- [x ] Every 5-10 minutes
- [ ] Manually triggered only
- [ ] Other: ___________

**Q7.2:** What scope of notes should be checked?
- [ ] All notes in vault
- [ ] Specific folder(s) (specify: _______)
- [ ] Notes with specific tag(s) (specify: _______)
- [x] Other: Only recently modified notes (within the past week)

**Q7.3:** Should users be notified when processing occurs?
- [x ] Yes, with desktop notifications
- [ ] Yes, with console/log output
- [ ] No, silent operation
- [ ] Other: ___________

**Q7.4:** What level of logging is needed?
- [ ] Minimal (errors only)
- [ ] Standard (errors + success confirmations)
- [x ] Verbose (all operations and debug info)
- [ ] Configurable

**Answer:**


## 8. Error Handling & Safety

**Q8.1:** How should the tool handle multiple @claude requests in one note?
- [] Process all requests in the note
- [x ] Process only the first unprocessed request
- [ ] Process N requests per run (specify N: _______)
- [ ] Other: ___________

**Q8.2:** Should @claude in code blocks or comments be ignored?
- [x ] Yes, ignore in code blocks (``` ```)
- [x ] Yes, ignore in HTML comments (<!-- -->)
- [ ] No, process everywhere
- [ ] Other: ___________

**Q8.3:** What should happen if tool execution fails?
- [x ] Append error message to note
- [ ] Retry X times (specify X: _______)
- [ ] Skip and move to next request
- [ ] Other: ___________

**Q8.4:** Should there be limits on response length?
- [x ] Yes, limit to X characters (specify: 5000)
- [ ] No limits
- [ ] Truncate with "view full response" link
- [ ] Other: ___________

**Answer:**


## 9. Cost & Usage Control

**Q9.1:** Should there be rate limiting to prevent excessive API calls?
- [x ] Yes, limit to X requests per hour (specify: 5)
- [ ] Yes, limit to X requests per note per day (specify: _______)
- [ ] No rate limiting
- [ ] Other: ___________

**Q9.2:** What should happen if Claude API is unavailable?
- [ ] Retry later automatically
- [ ] Log error and skip
- [x ] Notify user
- [ ] Other: ___________

**Answer:**


## 10. Additional Features (Optional)

**Q10.1:** Should the tool support any additional features?
- [ ] Undo/rollback of responses
- [ ] Response history/versioning
- [ ] Interactive mode (wait for user confirmation)
- [x ] Dry-run mode (show what would be done)
- [ ] Statistics/usage tracking
- [ ] Other: ___________

**Answer:**


---

## Additional Notes or Requirements

(Add any other thoughts, requirements, or considerations here)


