# Register your models here.
from django.contrib import admin

from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
)

admin.site.register(Project)
admin.site.register(Document)
admin.site.register(Cluster)
admin.site.register(ClusterElement)
admin.site.register(RefinementIteration)
admin.site.register(ProjectRefinement)
admin.site.register(TableChoice)
