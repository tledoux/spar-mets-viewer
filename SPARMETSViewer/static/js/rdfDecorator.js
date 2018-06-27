/**
 * Provide functions to allow decorations from SPARQL queries
 *
 * substituteRdfLabel(): function to substitute in all elements with class="rdfLabel"
 * the text with the label provided by the lookup attribute
 *
 * provideRdfTooltip(): function to add a title in all elements with class="rdfTooltip"
 * with the label provided by the text of the element itself
 *
 * Note: should be used with the tooltip addon for bootstrap
**/

  // Retrieve the label and insert it in the element
  var getLabel = function(prep, element) {
    $.getJSON('/labels/'+prep, function(data) { 
      var bindings = data.results.bindings;
      if (bindings === undefined || bindings.length == 0) {
        return
      }
      var label = bindings[0].label.value;
      if (label !== undefined) {
        var oldText = $(element).text();
        $(element).text(label + " (" + oldText + ")");
      }
    })
  }

  // Substitute all the rdfLabel with the equivalent in RDF database
  var substituteRdfLabel = function() {
    $(".rdfLabel").each(function(index, element) {
      var prep = $(element).attr("lookup");
      if (prep !== undefined) {
        getLabel(prep, element);
      }
    })
  }

  // Retrieve the label, insert it in the title attribute and activate the tooltip
  var getTooltip = function(prep, element) {
    $.getJSON('/labels/'+prep, function(data) {
      var bindings = data.results.bindings;
      if (bindings === undefined || bindings.length == 0) {
        return
      }
      var label = bindings[0].label.value;
      if (label !== undefined) {
        // console.log("Tooltip for " + prep + " is " + label);
        $(element).attr("title", label);
        $(element).tooltip();
      }
    })
  }

  // Add title attribute to all the rdfTooltip with the label in RDF database
  var provideRdfTooltip = function() {
    $(".rdfTooltip").each(function(index, element) {
      var prep = $(element).text();
      // console.log("Tooltip for " + prep);
      if (prep !== undefined) {
        getTooltip(prep, element);
      }
    })
  }
