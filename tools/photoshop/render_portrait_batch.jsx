/* Render transparent character PNGs through an open portrait template.
 * Set ADISCORD_PORTRAIT_JOBS to [{id, source, output, fit}] before evaluating.
 * Optional fit="contain" preserves source proportions inside the game canvas.
 * The working template is an in-memory snapshot; source documents stay open.
 */
(function () {
    var templateName = "ADISCORD portrait batch template";
    var template = null;
    var previousDocument = app.documents.length ? app.activeDocument : null;
    var previousDialogs = app.displayDialogs;
    var previousUnits = app.preferences.rulerUnits;
    var completed = [];
    for (var index = 0; index < app.documents.length; index++) {
        if (app.documents[index].name === templateName) {
            template = app.documents[index];
        }
    }
    if (!template) {
        throw new Error("Open an in-memory portrait template snapshot first.");
    }
    function layerEffects(layer) {
        app.activeDocument.activeLayer = layer;
        var reference = new ActionReference();
        reference.putProperty(charIDToTypeID("Prpr"), stringIDToTypeID("layerEffects"));
        reference.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        var descriptor = executeActionGet(reference);
        return descriptor.hasKey(stringIDToTypeID("layerEffects")) ?
            descriptor.getObjectValue(stringIDToTypeID("layerEffects")) : null;
    }
    function applyEffects(layer, effects) {
        if (!effects) return;
        app.activeDocument.activeLayer = layer;
        var reference = new ActionReference();
        reference.putProperty(charIDToTypeID("Prpr"), stringIDToTypeID("layerEffects"));
        reference.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
        var descriptor = new ActionDescriptor();
        descriptor.putReference(charIDToTypeID("null"), reference);
        descriptor.putObject(charIDToTypeID("T   "), stringIDToTypeID("layerEffects"), effects);
        executeAction(charIDToTypeID("setd"), descriptor, DialogModes.NO);
    }
    try {
        app.displayDialogs = DialogModes.NO;
        app.preferences.rulerUnits = Units.PIXELS;
        for (var jobIndex = 0; jobIndex < ADISCORD_PORTRAIT_JOBS.length; jobIndex++) {
            var job = ADISCORD_PORTRAIT_JOBS[jobIndex];
            var work = template.duplicate("portrait-export-" + job.id, false);
            var source = null;
            try {
                app.activeDocument = work;
                var group = work.layerSets.getByName("Group 1");
                var placeholder = null;
                for (var layerIndex = 0; layerIndex < group.artLayers.length; layerIndex++) {
                    var layer = group.artLayers[layerIndex];
                    if (layer.kind === LayerKind.NORMAL && layer.visible && !layer.grouped && !placeholder) {
                        placeholder = layer;
                    }
                }
                if (!placeholder) throw new Error("Missing visible portrait layer.");
                var effects = layerEffects(placeholder);
                for (var hideIndex = group.artLayers.length - 1; hideIndex >= 0; hideIndex--) {
                    if (group.artLayers[hideIndex].kind === LayerKind.NORMAL) {
                        group.artLayers[hideIndex].remove();
                    }
                }
                source = app.open(new File(job.source));
                if (job.fit === "contain") {
                    var scale = Math.min(156 / source.width.as("px"), 210 / source.height.as("px"));
                    source.resizeImage(UnitValue(Math.round(source.width.as("px") * scale), "px"),
                        UnitValue(Math.round(source.height.as("px") * scale), "px"), null, ResampleMethod.BICUBICSHARPER);
                    source.resizeCanvas(UnitValue(156, "px"), UnitValue(210, "px"), AnchorPosition.BOTTOMCENTER);
                } else {
                    source.resizeImage(UnitValue(156, "px"), UnitValue(210, "px"), null, ResampleMethod.BICUBICSHARPER);
                }
                var imported = source.activeLayer.duplicate(work, ElementPlacement.PLACEATBEGINNING);
                source.close(SaveOptions.DONOTSAVECHANGES);
                source = null;
                app.activeDocument = work;
                imported.name = job.id;
                imported.move(group, ElementPlacement.PLACEATEND);
                imported = group.artLayers.getByName(job.id);
                imported.visible = true;
                if (imported.grouped) imported.grouped = false;
                applyEffects(imported, effects);
                for (var adjustmentIndex = 0; adjustmentIndex < group.artLayers.length; adjustmentIndex++) {
                    if (group.artLayers[adjustmentIndex].kind !== LayerKind.NORMAL && !group.artLayers[adjustmentIndex].grouped) {
                        group.artLayers[adjustmentIndex].grouped = true;
                    }
                }
                var output = new File(job.output);
                if (!output.parent.exists) output.parent.create();
                var png = new PNGSaveOptions();
                png.interlaced = false;
                work.saveAs(output, png, true, Extension.LOWERCASE);
                completed.push(job.id);
            } finally {
                if (source) source.close(SaveOptions.DONOTSAVECHANGES);
                work.close(SaveOptions.DONOTSAVECHANGES);
            }
        }
    } finally {
        app.displayDialogs = previousDialogs;
        app.preferences.rulerUnits = previousUnits;
        if (previousDocument) app.activeDocument = previousDocument;
    }
    return completed.join("\n");
}());
