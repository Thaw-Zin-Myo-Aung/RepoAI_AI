package th.ac.mfu.repoai.domain.branchdto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record BranchSummary(
        String name,
        CommitRef commit,
        @JsonProperty("protected") boolean protectedBranch,
        Protection protection,
        @JsonProperty("protection_url") String protectionUrl) {
}