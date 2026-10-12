#target photoshop

// Run with File > Scripts > Browse. Creates an unsaved, layered document.
// Geometry is authored at 4x the intended 130 px export size.
(function () {
    var previousUnits = app.preferences.rulerUnits;
    var previousDialogs = app.displayDialogs;
    var doc;

    function color(hex) {
        var value = new SolidColor();
        value.rgb.hexValue = hex;
        return value;
    }

    function group(name) {
        var result = doc.layerSets.add();
        result.name = name;
        return result;
    }

    function layer(parent, name) {
        var result = parent.artLayers.add();
        result.name = name;
        doc.activeLayer = result;
        return result;
    }

    function polygon(points, hex) {
        doc.selection.select(points, SelectionType.REPLACE, 0, true);
        doc.selection.fill(color(hex), ColorBlendMode.NORMAL, 100, false);
        doc.selection.deselect();
    }

    function ellipse(cx, cy, rx, ry, hex) {
        var points = [];
        for (var i = 0; i < 96; i++) {
            var angle = i * Math.PI * 2 / 96;
            points.push([cx + Math.cos(angle) * rx, cy + Math.sin(angle) * ry]);
        }
        polygon(points, hex);
    }

    function rectangle(x, y, width, height, hex) {
        polygon([[x, y], [x + width, y], [x + width, y + height], [x, y + height]], hex);
    }

    function mix(start, end, amount) {
        var result = "";
        for (var i = 0; i < 6; i += 2) {
            var a = parseInt(start.substr(i, 2), 16);
            var b = parseInt(end.substr(i, 2), 16);
            var part = Math.round(a + (b - a) * amount).toString(16);
            result += part.length < 2 ? "0" + part : part;
        }
        return result;
    }

    function leaf(cx, cy, angle, length, width) {
        var local = [[0, 0], [-width, -length * 0.40], [-width * 0.65, -length * 0.75],
            [0, -length], [width * 0.65, -length * 0.75], [width, -length * 0.40]];
        var points = [];
        for (var i = 0; i < local.length; i++) {
            points.push([
                cx + local[i][0] * Math.cos(angle) - local[i][1] * Math.sin(angle),
                cy + local[i][0] * Math.sin(angle) + local[i][1] * Math.cos(angle)
            ]);
        }
        polygon(points, "263746");
        polygon([points[0], points[1], points[2], points[3]], "829baa");
        polygon([points[0], points[2], points[3]], "c0d0d7");
    }

    try {
        app.preferences.rulerUnits = Units.PIXELS;
        app.displayDialogs = DialogModes.NO;
        doc = app.documents.add(520, 520, 72, "Cold steel focus - editable example",
            NewDocumentMode.RGB, DocumentFill.TRANSPARENT, 1, BitsPerChannelType.EIGHT);
        var initialLayer = doc.activeLayer;

        var backdrop = layer(doc, "00 - Preview background - hidden for export");
        rectangle(0, 0, 520, 520, "34393f");
        backdrop.visible = false;
        initialLayer.remove();

        var atmosphere = group("01 - Shadow and cold halo");
        var groundShadow = layer(atmosphere, "Ground shadow");
        ellipse(260, 414, 158, 23, "05090e");
        groundShadow.applyGaussianBlur(12);
        groundShadow.opacity = 75;
        var halo = layer(atmosphere, "Blue halo");
        ellipse(260, 247, 170, 170, "759ac2");
        halo.applyGaussianBlur(20);
        halo.opacity = 25;

        var medallion = group("02 - Metal medallion");
        layer(medallion, "Outer rim");
        ellipse(260, 250, 164, 164, "111a24");
        ellipse(260, 247, 159, 159, "7892a7");
        ellipse(260, 244, 153, 153, "d1e0ea");
        ellipse(260, 248, 148, 148, "30495e");

        layer(medallion, "Blue radial light");
        // Nested discs move towards the light while staying inside the rim.
        for (var step = 0; step <= 90; step++) {
            var t = step / 90;
            ellipse(260 + 35 * t, 248 - 43 * t, 145 * (1 - t) + 1,
                145 * (1 - t) + 1, mix("344e69", "e4edf1", t));
        }

        var wreath = group("03 - Laurel wreath");
        for (var side = -1; side <= 1; side += 2) {
            layer(wreath, side < 0 ? "Left silver leaves" : "Right silver leaves");
            for (var j = 0; j < 9; j++) {
                var theta = (25 + j * 12) * Math.PI / 180;
                var x = 260 + side * Math.sin(theta) * 177;
                var y = 247 + Math.cos(theta) * 177;
                leaf(x, y, side * (0.72 - j * 0.15), 45, 10);
            }
        }

        var example = group("04 - EXAMPLE factory - hide to use your own image");
        layer(example, "Factory silhouette");
        polygon([[112, 382], [112, 305], [155, 278], [155, 304], [204, 279],
            [204, 309], [253, 285], [253, 324], [340, 324], [380, 359],
            [398, 409], [133, 409]], "182632");
        rectangle(158, 144, 28, 186, "1d2c3b");
        rectangle(227, 195, 22, 148, "263949");
        rectangle(290, 234, 19, 113, "30485a");
        rectangle(338, 260, 16, 99, "273d4e");

        layer(example, "Steel faces and edge highlights");
        rectangle(158, 144, 7, 158, "a1b7c7");
        rectangle(166, 144, 7, 158, "566f85");
        rectangle(227, 195, 5, 112, "92aabd");
        rectangle(290, 234, 4, 93, "9ab2c2");
        rectangle(338, 260, 3, 74, "7c97ac");
        polygon([[112, 305], [155, 278], [155, 284], [112, 311]], "b4c6d1");
        polygon([[155, 304], [204, 279], [204, 285], [155, 310]], "8fa9bc");
        polygon([[204, 309], [253, 285], [253, 291], [204, 315]], "839fb2");
        for (var row = 0; row < 2; row++) {
            for (var column = 0; column < 7; column++) {
                rectangle(127 + column * 31, 335 + row * 26, 12, 15, "698a9f");
                rectangle(127 + column * 31, 335 + row * 26, 12, 3, "bdd0d8");
            }
        }

        var subject = group("05 - YOUR CUTOUT - place transparent image here");
        layer(subject, "Place your building, portrait or vehicle here");

        var foreground = group("06 - Foreground");
        layer(foreground, "Faceted rubble - optional");
        for (var stone = 0; stone < 17; stone++) {
            var sx = 106 + stone * 18;
            var sy = 392 + Math.sin(stone * 2.7) * 13;
            polygon([[sx - 12, sy + 12], [sx - 7, sy - 5], [sx + 9, sy - 10],
                [sx + 18, sy + 6], [sx + 8, sy + 15]], "233747");
            polygon([[sx - 7, sy - 5], [sx + 9, sy - 10], [sx + 5, sy + 3]], "90a9b9");
        }
        var mist = layer(foreground, "Soft ground haze - optional");
        ellipse(260, 411, 142, 8, "859eaf");
        mist.applyGaussianBlur(10);
        mist.opacity = 22;

        doc.activeLayer = subject.artLayers[0];
        alert("The layered example is ready.\n\n" +
            "Hide group 04 to replace the factory. Put your transparent cutout in group 05.\n" +
            "Layer 00 is a hidden preview background. Keep it hidden for export.\n\n" +
            "Save the master as PSD. Resize a COPY to 130 x 130 px and export as transparent PNG.\n" +
            "No files have been saved automatically.");
    } catch (error) {
        alert("Could not finish the focus example.\n" + error.message +
            "\nLine: " + error.line + "\nAny partial document remains open.");
    } finally {
        app.preferences.rulerUnits = previousUnits;
        app.displayDialogs = previousDialogs;
    }
}());
