/**
 * Provide functions for common functionnalities
 *
 * numberFormatter(): function to properly format number
 *   Should provide a 'units' array if necessary (i.e. translation)
 *
 * sizeFormatter(): function to format size of file
 *
 * getCurrentYearMonth() : retrieve current year and month in YYYY-mm format
 *
 * showError(): show a error message in the #msgerr field with a fading #alertMsg div
 *
 * translateNs() : simplify an URI with known prefixes
 *
**/


  // Format a number with space separator
  var numberFormatter = function(value) {
    return String(value).replace(/(.)(?=(\d{3})+$)/g,'$1 ')
  }

  // Format a size for humans
  var sizeFormatter = function(value) {
    if (units == undefined) {
      units = ['bytes', 'KB', 'MB', 'GB', 'TB']
    }
    if (value == 0) return '0';
    var i = parseInt(Math.floor(Math.log(value) / Math.log(1000)));
    var r = (value / Math.pow(1000, i));
    if (r >= 99.995 ||  i == 0) {
      return r.toFixed(0) + ' ' + units[i];
    } else {
      return r.toFixed(2) + ' ' + units[i];
    }
  }

  var getCurrentYearMonth = function() {
    function pad(num) {
      if (num < 10) { return '0' + num; } else { return num; }
    }
    var d = new Date();
    return d.getFullYear() + '-' + pad(d.getMonth() + 1);
  }


  var showError = function(msg) {
      $("#msgerr").text(msg)
      $("#alertMsg").fadeTo(2000, 500).slideUp(500, function() {
        $("#alertMsg").slideUp(500);
      });
  }

  var translateNs = function(original) {
    if (original == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
      return "a"
    if (original.startsWith("info:bnf/spar/structure#"))
      return original.replace("info:bnf/spar/structure#", "sparstructure:")
    if (original.startsWith("info:bnf/spar/context#"))
      return original.replace("info:bnf/spar/context#", "sparcontext:")
    if (original.startsWith("info:bnf/spar/provenance#"))
      return original.replace("info:bnf/spar/provenance#", "sparprovenance:")
    if (original.startsWith("info:bnf/spar/representation#"))
      return original.replace("info:bnf/spar/representation#", "sparrepresentation:")
    if (original.startsWith("info:bnf/spar/reference#"))
      return original.replace("info:bnf/spar/reference#", "sparreference:")
    if (original.startsWith("info:bnf/spar/fixity#"))
      return original.replace("info:bnf/spar/fixity#", "sparfixity:")
    if (original.startsWith("info:bnf/spar/textmd#"))
      return original.replace("info:bnf/spar/textmd#", "textmd:")
    if (original.startsWith("http://www.openarchives.org/ore/terms/"))
      return original.replace("http://www.openarchives.org/ore/terms/", "oai-ore:")
    if (original.startsWith("http://purl.org/dc/elements/1.1/"))
      return original.replace("http://purl.org/dc/elements/1.1/", "dc:")
    if (original.startsWith("http://www.w3.org/2000/01/rdf-schema#"))
      return original.replace("http://www.w3.org/2000/01/rdf-schema#", "rdfs:")
    if (original.startsWith("http://www.w3.org/2002/07/owl#"))
      return original.replace("http://www.w3.org/2002/07/owl#", "owl:")
    if (original.startsWith("http://xmlns.com/foaf/0.1/"))
      return original.replace("http://xmlns.com/foaf/0.1/", "foaf:")
    if (original.startsWith("info:bnf/spar/provenance/"))
      return original.replace("info:bnf/spar/provenance/", "event:")
    // Simplify ark URIs
    if (original.startsWith("ark:/")) {
      var reV = /\.version/;
      var reR = /\.release/;
      var reNum = /\/([a-z]+)\d+([\.\/])/;
      return original.replace(reV, ".V").replace(reR, '.R').replace(reNum, '/$1XXX$2')
    }
    return original
  }
