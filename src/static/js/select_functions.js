let id_article_shown = '0';

function escapeHtml(unsafe)
{
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
 }

// show the article when click on cluster
function article_show(article_id)
{
    document.getElementById("article_details").style.visibility = 'visible';
    // hide the previous article
    if(id_article_shown != '0')
    {
        document.getElementById(id_article_shown).style.visibility='hidden';
    }
    // display the article
    document.getElementById(article_id).style.visibility='visible';
    id_article_shown = article_id
    // make the scroll to top
    document.getElementById("article_details").scrollTop = 0;
}


function light(element)
{
    element.style.filter= "brightness(4000000)";
    element.style.width ="20px"
    element.style.height ="20px"
    element.style.zIndex = "1";
}

function dark(element)
{
    element.style.width ="10px"
    element.style.height ="15px"
    element.style.filter= "brightness(1)"
    element.style.zIndex = "0";
}

function light_cluster(topic)
{
    var graphic = document.getElementById("cluster_display")
    var points = graphic.getElementsByClassName(topic)
    for (let i = 0; i< points.length;i++)
    {
        light(points[i])
    }

}

function dark_cluster(topic)
{
    let graphic = document.getElementById("cluster_display")
    let points = graphic.getElementsByClassName("topic_"+topic)
    for (let i = 0; i< points.length;i++)
    {
        dark(points[i])
    }

}




//check, uncheck all
function toggle(source) {
   /*
+   * Toggle the checkboxes based on the state of the source checkbox.
+   * Update the counter based on the number of checkboxes toggled.
+   */

    const checkboxes = document.getElementsByName('check_row');
    let addValue = -1;
    if(source.checked){
        addValue = 1
    }
    let c = 0;
    for(var i=0, n=checkboxes.length;i<n;i++) {
      if (!(checkboxes[i].checked == source.checked)){
        checkboxes[i].checked = source.checked;
        c = c + addValue;
      }
    }
    let counter = document.querySelector(".article-counter");
    let counterBottom = document.querySelector(".article-counter-bottom");
    let p = parseInt(counter.textContent);
    counter.textContent = p + c;
    counterBottom.textContent = p + c;
  }
