// define indexOf for IE (code from https://developer.mozilla.org/en/JavaScript/Reference/Global_Objects/Array/indexOf)
if (!Array.prototype.indexOf)
{
  Array.prototype.indexOf = function(searchElement /*, fromIndex */)
  {
    "use strict";

    if (this === void 0 || this === null)
      throw new TypeError();

    var t = Object(this);
    var len = t.length >>> 0;
    if (len === 0)
      return -1;

    var n = 0;
    if (arguments.length > 0)
    {
      n = Number(arguments[1]);
      if (n !== n) // shortcut for verifying if it's NaN
        n = 0;
      else if (n !== 0 && n !== (1 / 0) && n !== -(1 / 0))
        n = (n > 0 || -1) * Math.floor(Math.abs(n));
    }

    if (n >= len)
      return -1;

    var k = n >= 0
          ? n
          : Math.max(len - Math.abs(n), 0);

    for (; k < len; k++)
    {
      if (k in t && t[k] === searchElement)
        return k;
    }
    return -1;
  };
}
if($('#commit_graph')){
    var data;
    var offset = 0;
    var selected_commit = -1;
    var y_offset = 0;
    var page_size = 14;
    var limit = 14;
    var tree, next_column, max_x_pos, max_row;

    // graph size settings
    var x_space = 10;
    var y_space = 20;
    var point_offset = 5;
    var point_size = 10;

    var $first = $('#first');
    var $last = $('#last');
    var $canvas = $('#commit_graph');
    var $highlighter = $('#commit_highlighter');
    var highlighter = $highlighter[0];
    var canvas = $canvas[0];
    var highlighter_ctx = highlighter.getContext('2d');
    var canvas_ctx = canvas.getContext('2d');

    // graph set up
    var height = (limit + 0.5) * y_space;
    var commit_rows = [];
    var taken_coords = {};
    canvas.height=height;

    // highlighter set up
    highlighter.height=height;
    highlighter_ctx.fillStyle = "#ccc";

    $.getJSON(document.location.href+'_data', function(data) {
        data = data;
        tree = data['built_tree'];
        next_column = data['next_column'];
        max_x_pos = x_space*next_column;
        max_row = data['max_row']

        // Calculate the (x,y) positions of all the commits
        for(var c in tree){
            var commit = tree[c];
            var x_pos = x_space+(commit.column*x_space);
            var y_pos = y_space+((commit.row)*y_space);
            if (!taken_coords[x_pos]){
                taken_coords[x_pos] = [y_pos]
            }
            else if(taken_coords[x_pos].indexOf(y_pos) == -1){
                taken_coords[x_pos].push(y_pos);
            }
            commit_rows[commit.row] = {
                url: commit.url,
                x_pos: x_pos,
                y_pos: y_pos }
        }
        updateOffset(0);
        selectCommit(0);
    });
    updateOffset = function(x) {
        $first.removeClass('disabled');
        $last.removeClass('disabled');
        offset = x;
        if(offset <= 1) {
            offset = 1;
            $last.addClass('disabled');
        }
        else if(offset > (max_row-page_size)) {
            offset = max_row - page_size;
            $first.addClass('disabled');
        }
        y_offset = offset * y_space;
        drawGraph(offset);
        if (selected_commit >= offset-1 && selected_commit <= offset + page_size) {
          selectCommit(selected_commit);
        }
        return false;
    };
    $last.click(function() {
        return updateOffset(0);
    });
    $first.click(function() {
        return updateOffset(max_row);
    });

    function selectCommit(index) {
        var commit = commit_rows[index];
        highlighter_ctx.clearRect(0, 0, canvas.width, canvas.height);
        // active_ys = [commit.y_pos-y_space/4,y_space]
        highlighter_ctx.fillRect(
            0, (commit.y_pos - y_offset) - y_space/4,
            750, y_space)
        if (selected_commit != index) {
          $('#commit_view').html('<em>Loading commit details...</em>');
          $.get(commit.url+'basic',function(result){
              $('#commit_view').html(result);
          });
        }
        selected_commit = index;
    }

    $canvas.click(function(evt) {
        var y = Math.floor((evt.pageY-$canvas.offset().top) / y_space);
        selectCommit(offset+y-1);
    });

    function drawGraph(offset) {
        // Clear the canvas and set the contetx
        var canvas_ctx = canvas.getContext('2d');
        highlighter_ctx.clearRect(0, 0, canvas.width, canvas.height);
        canvas_ctx.clearRect(0, 0, canvas.width, canvas.height);
        canvas_ctx.fillStyle = "rgb(0,0,0)";
        canvas_ctx.lineWidth = 1;
        canvas_ctx.lineJoin = 'round';
        canvas_ctx.textBaseline = "top";
        canvas_ctx.font = "12px sans-serif";

        for(var c in tree){
            var commit = tree[c];
            var x_pos = x_space+(commit.column*x_space);
            var y_pos = y_space+((commit.row-offset)*y_space);

            for(var i=0,len=commit.parents.length;i<len;i++){
                var parent = tree[commit.parents[i]];
                var parent_x = x_space+parent.column*x_space
                var parent_y = y_space+(parent.row-offset)*y_space;

                switch(parent.column % 6){
                case 0:
                    canvas_ctx.strokeStyle = "#a00";
                    break;
                case 1:
                    canvas_ctx.strokeStyle = "#0a0";
                    break;
                case 2:
                    canvas_ctx.strokeStyle = "#00a";
                    break;
                case 3:
                    canvas_ctx.strokeStyle = "#aa0";
                    break;
                case 4:
                    canvas_ctx.strokeStyle = "#0aa";
                    break;
                default:
                    canvas_ctx.strokeStyle = "#f0f";
                }

                // Vertical
                canvas_ctx.beginPath();
                canvas_ctx.moveTo(parent_x+point_offset, y_pos+y_space);
                canvas_ctx.lineTo(parent_x+point_offset, parent_y+point_offset);
                canvas_ctx.stroke();

                // Diagonal
                canvas_ctx.beginPath()
                canvas_ctx.moveTo(x_pos + point_offset, y_pos+point_offset);
                canvas_ctx.lineTo(parent_x+point_offset, y_pos+y_space);
                canvas_ctx.stroke();
            }
        }
        // draw commit points and message text
        canvas_ctx.fillStyle = "rgb(0,0,0)";
        for(var c in tree){
            var commit = tree[c];
            var x_pos = x_space+(commit.column*x_space);
            var y_pos = y_space+((commit.row-offset)*y_space);

            switch(commit.column % 6){
                case 0:
                    canvas_ctx.strokeStyle = canvas_ctx.fillStyle = "#a00";
                    break;
                case 1:
                    canvas_ctx.strokeStyle = canvas_ctx.fillStyle = "#0a0";
                    break;
                case 2:
                    canvas_ctx.strokeStyle = canvas_ctx.fillStyle = "#00a";
                    break;
                case 3:
                    canvas_ctx.strokeStyle = canvas_ctx.fillStyle = "#aa0";
                    break;
                case 4:
                    canvas_ctx.strokeStyle = canvas_ctx.fillStyle = "#0aa";
                    break;
                default:
                    canvas_ctx.strokeStyle = canvas_ctx.fillStyle = "#f0f";
                }

            canvas_ctx.beginPath();
            canvas_ctx.arc(x_pos + point_offset, y_pos + point_offset, point_offset, 0, 2 * Math.PI, false);
            canvas_ctx.fill();
            canvas_ctx.stroke();
            canvas_ctx.fillStyle = "#000";
            canvas_ctx.fillText(commit.message, (1+next_column) * x_space, y_pos);
        }
    }

    function scroll(event) {
      var delta = 0;
      var e = event.originalEvent;
      if (e.type == "mousewheel") {
        delta = -(e.wheelDelta / 40);
      } else if (e.type == "DOMMouseScroll") {
        // firefox
        delta = e.detail;
      }
      updateOffset(offset + delta);
      return false;
    }

    $canvas.bind("mousewheel", scroll);
    $canvas.bind("DOMMouseScroll", scroll);
}
