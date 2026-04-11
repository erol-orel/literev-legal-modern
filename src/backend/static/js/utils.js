// utils functions for previousgraph page

function isFilterObjectEmpty(obj) {
    for (let prop in obj) {
      for (let _prop in prop){
        if (obj.hasOwnProperty(_prop)) {
          return false;
        }
      }
    }
    return true;
  }
