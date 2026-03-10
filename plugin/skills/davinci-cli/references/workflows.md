# Common Workflows

## Color Grading Pipeline

```bash
# 1. Get clip indices
dr clip list --fields index,name

# 2. Save a checkpoint (Resolve API has NO undo!)
dr color version add 1 "before-edit" --dry-run
dr color version add 1 "before-edit"

# 3. Apply LUT
dr color apply-lut 1 /path/to/lut.cube --dry-run
dr color apply-lut 1 /path/to/lut.cube

# 4. Copy grade to another clip
dr color copy-grade --from 1 --to 2 --dry-run
dr color copy-grade --from 1 --to 2

# 5. If unhappy, load the saved version
dr color version load 1 "before-edit"
```

> **Note:** `copy-grade` copies directly from source to destination. There is no separate paste step.

## Render / Deliver Pipeline

```bash
# 1. Check available presets
dr deliver preset list

# 2. Load a preset
dr deliver preset load "YouTube 1080p"

# 3. Add a render job
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}' --dry-run
dr deliver add-job --json '{"output_dir": "/output", "filename": "final"}'

# 4. Start rendering (always dry-run first!)
dr deliver start --dry-run
dr deliver start

# 5. Monitor progress (poll interval >= 5s)
dr deliver status
```

## Media Organization

```bash
# 1. List current media pool
dr media list --fields clip_name,file_path

# 2. Create a folder
dr media folder create "B-Roll"

# 3. Import files
dr media import /path/to/file1.mov /path/to/file2.mp4

# 4. Move to folder
dr media move --clip-names "file1.mov,file2.mp4" --target-folder "B-Roll" --dry-run
dr media move --clip-names "file1.mov,file2.mp4" --target-folder "B-Roll"
```

## Timeline Management

```bash
# 1. List timelines
dr timeline list --fields name

# 2. Switch to a timeline
dr timeline switch "Main Edit" --dry-run
dr timeline switch "Main Edit"

# 3. Duplicate for safety
dr timeline duplicate --name "Main Edit - Copy" --dry-run
dr timeline duplicate --name "Main Edit - Copy"

# 4. List clips in the timeline
dr clip list --fields index,name

# 5. Get current timecode
dr timeline timecode get
```

## Gallery Still Management

```bash
# 1. List gallery albums
dr gallery album list

# 2. Set current album
dr gallery album set "Stills" --dry-run
dr gallery album set "Stills"

# 3. Grab a still from current clip
dr color still grab 1 --dry-run
dr color still grab 1

# 4. Export stills
dr gallery still export --folder-path /output/stills --format png --dry-run
dr gallery still export --folder-path /output/stills --format png
```
